from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.helpers import extract_trainer_references
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    LocationConnection,
    LocationItem,
    LocationScriptAwardedItem,
    LocationShop,
    LocationShopItem,
    LocationStaticEncounter,
    LocationWarp,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


def _build_gen5_special_vendor_shop(
    vendor: Any,
    item_names_by_id: dict[int, str],
    *,
    script_file_id: int,
    command_offset: int,
    selector_id: int | None = None,
    mode: int | None = None,
) -> LocationShop:
    missing_item_ids = [
        item.item_id for item in vendor.items if item.item_id not in item_names_by_id
    ]
    if missing_item_ids:
        source = f"selector {selector_id}" if selector_id is not None else vendor.name
        raise DataSourceError(
            f"Special vendor {source} references unknown items: {missing_item_ids}"
        )
    selector_ids = vendor.selector_ids
    if not selector_ids and selector_id is not None:
        selector_ids = (selector_id,)
    return LocationShop(
        kind=vendor.kind,
        currency=vendor.currency,
        inventory_id=None,
        script_file_id=script_file_id,
        command_offset=command_offset,
        items=tuple(
            LocationShopItem(
                item_id=item.item_id,
                name=item_names_by_id[item.item_id],
                price=item.price,
                required_badges=None,
                availability=item.availability,
            )
            for item in vendor.items
        ),
        name=vendor.name,
        is_main_game=vendor.is_main_game,
        selector_id=selector_id,
        mode=mode,
        dynamic=vendor.dynamic,
        inventory_source="runtime" if vendor.dynamic else "engine-rule",
        availability=vendor.availability,
        vendor_id=vendor.vendor_id,
        selector_ids=selector_ids,
    )


@dataclass(frozen=True)
class _ArchiveLocationSource:
    profile: Any
    engine: Any
    rom_sha256: str
    map_headers_path: str
    map_names_member: int
    overworld_objects_path: str
    map_matrices_path: str
    scripts_path: str
    messages_path: str
    map_headers: Any
    messages: Any
    headers: tuple[Any, ...]
    script_file_ids: tuple[int, ...]
    overworld_objects: Any
    map_matrices: Any
    scripts: Any
    unused_overworld_members: frozenset[int]


@dataclass(frozen=True)
class _ArchiveLocationRelationships:
    trainers_by_header: dict[int, list[Any]]
    static_encounters_by_header: dict[int, list[LocationStaticEncounter]]
    npc_trades_by_header: dict[int, list[dict[str, Any]]]
    script_awarded_items_by_header: dict[int, list[LocationScriptAwardedItem]]
    connections_by_header: dict[int, list[LocationConnection]]


@dataclass(frozen=True)
class _ArchiveLocationCatalogs:
    item_names_by_id: dict[int, str]
    item_prices_by_id: dict[int, int | None]
    shops_by_id: dict[int, dict[str, Any]]

    @property
    def item_count(self) -> int:
        return max(self.item_names_by_id, default=-1) + 1


def extract_archive_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = _load_archive_location_source(result)
    relationships = _collect_archive_location_relationships(
        result,
        source,
        trainer_dataset=trainer_dataset,
        static_encounter_dataset=static_encounter_dataset,
        trade_dataset=trade_dataset,
        item_dataset=item_dataset,
    )
    catalogs = _build_archive_location_catalogs(item_dataset, mart_dataset)
    records, unsupported_shop_selectors = _build_archive_location_records(
        source, relationships, catalogs
    )
    return _build_archive_location_envelope(source, records, unsupported_shop_selectors)


def _load_archive_location_source(
    result: InspectionResult,
) -> _ArchiveLocationSource:
    profile = result.match.profile
    try:
        map_headers_path = profile.layout["map_headers"]
        map_names_member = profile.parameters["map_names_member"]
        overworld_objects_path = profile.layout["overworld_objects"]
        map_matrices_path = profile.layout["map_matrices"]
        scripts_path = profile.layout["scripts"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    field_archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        field_archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        field_archive_options["allow_trailing_data"] = True

    messages_path = profile.layout["messages"]
    map_headers = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    headers = engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
    )
    script_file_ids = engine.parse_map_header_script_files(map_headers.read(0))
    overworld_objects = platform.archive_cls.from_bytes(
        filesystem.read(overworld_objects_path), **field_archive_options
    )
    map_matrices = platform.archive_cls.from_bytes(filesystem.read(map_matrices_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **field_archive_options
    )
    return _ArchiveLocationSource(
        profile=profile,
        engine=engine,
        rom_sha256=result.image.hashes.sha256,
        map_headers_path=map_headers_path,
        map_names_member=map_names_member,
        overworld_objects_path=overworld_objects_path,
        map_matrices_path=map_matrices_path,
        scripts_path=scripts_path,
        messages_path=messages_path,
        map_headers=map_headers,
        messages=messages,
        headers=headers,
        script_file_ids=script_file_ids,
        overworld_objects=overworld_objects,
        map_matrices=map_matrices,
        scripts=scripts,
        unused_overworld_members=frozenset(
            profile.parameters.get("overworld_objects_unused", ())
        ),
    )


def _collect_archive_location_relationships(
    result: InspectionResult,
    source: _ArchiveLocationSource,
    *,
    trainer_dataset: dict[str, Any] | None,
    static_encounter_dataset: dict[str, Any] | None,
    trade_dataset: dict[str, Any] | None,
    item_dataset: dict[str, Any] | None,
) -> _ArchiveLocationRelationships:
    script_headers = _resolve_gen5_script_locations(
        source.engine,
        source.headers,
        source.script_file_ids,
        source.scripts,
        source.overworld_objects,
        unused_overworld_members=source.unused_overworld_members,
    )
    return _ArchiveLocationRelationships(
        trainers_by_header=extract_trainer_references(result, trainer_dataset),
        static_encounters_by_header=_extract_static_encounter_references(
            source.engine,
            source.profile,
            source.messages,
            script_headers,
            static_encounter_dataset,
        ),
        npc_trades_by_header=_extract_gen5_npc_trade_references(
            source.engine,
            source.profile,
            source.messages,
            source.map_headers.read(0),
            source.scripts,
            script_headers,
            trade_dataset,
            item_dataset,
        ),
        script_awarded_items_by_header=_extract_gen5_script_awarded_items(
            source.engine,
            source.scripts,
            script_headers,
            item_dataset,
        ),
        connections_by_header=_extract_encounter_map_connections(
            source.engine, source.headers, source.map_matrices
        ),
    )


def _build_archive_location_catalogs(
    item_dataset: dict[str, Any] | None,
    mart_dataset: dict[str, Any] | None,
) -> _ArchiveLocationCatalogs:
    return _ArchiveLocationCatalogs(
        item_names_by_id={
            record["item_id"]: record["name"]
            for record in (item_dataset or {}).get("records", ())
        },
        item_prices_by_id={
            record["item_id"]: record.get("price")
            for record in (item_dataset or {}).get("records", ())
        },
        shops_by_id={
            record["shop_id"]: record
            for record in (mart_dataset or {}).get("records", ())
        },
    )


def _build_archive_location_records(
    source: _ArchiveLocationSource,
    relationships: _ArchiveLocationRelationships,
    catalogs: _ArchiveLocationCatalogs,
) -> tuple[list[dict[str, Any]], list[int]]:
    headers_by_id = {header.header_id: header for header in source.headers}
    try:
        visible_member = source.profile.parameters["item_balls_script_member"]
        hidden_member = source.profile.parameters["hidden_items_script_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {source.profile.id!r} is missing field-item metadata: {error.args[0]}"
        ) from error
    visible_item_ids = source.engine.parse_visible_item_script_table(
        source.scripts.read(visible_member)
    )
    hidden_item_ids = source.engine.parse_hidden_item_script_table(
        source.scripts.read(hidden_member)
    )
    records = []
    unsupported_shop_selectors = []
    for header in source.headers:
        record, unsupported_selectors = _build_archive_location_record(
            source,
            relationships,
            catalogs,
            headers_by_id,
            header,
            visible_item_ids,
            hidden_item_ids,
        )
        records.append(record)
        unsupported_shop_selectors.extend(unsupported_selectors)
    return records, unsupported_shop_selectors


def _build_archive_location_record(
    source: _ArchiveLocationSource,
    relationships: _ArchiveLocationRelationships,
    catalogs: _ArchiveLocationCatalogs,
    headers_by_id: dict[int, Any],
    header: Any,
    visible_item_ids: tuple[int | None, ...],
    hidden_item_ids: tuple[int | None, ...],
) -> tuple[dict[str, Any], list[int]]:
    section_name, section_name_source = resolve_location_section(
        source.profile,
        header_id=header.header_id,
        internal_name=None,
    )
    script_file_id = source.script_file_ids[header.header_id]
    overworld_data = _read_overworld_data(source, header)
    items = (
        _extract_gen5_field_items(
            source.engine,
            overworld_data,
            catalogs,
            visible_item_ids=visible_item_ids,
            hidden_item_ids=hidden_item_ids,
        )
        if overworld_data is not None
        else []
    )
    if overworld_data is None:
        shops: list[LocationShop] = []
        seen_vendor_ids: set[str] = set()
        unsupported_shop_selectors: list[int] = []
    else:
        shops, seen_vendor_ids, unsupported_shop_selectors = _extract_gen5_script_shops(
            source, catalogs, script_file_id
        )
    shops.extend(
        _extract_gen5_location_vendors(
            source.engine,
            header.header_id,
            catalogs.item_names_by_id,
            script_file_id,
            seen_vendor_ids,
        )
    )
    warps = _extract_gen5_location_warps(source, overworld_data, headers_by_id)
    return (
        replace(
            header,
            section_name=section_name,
            section_name_source=section_name_source,
            trainers=tuple(relationships.trainers_by_header.get(header.header_id, ())),
            warps=tuple(warps),
            static_encounters=tuple(
                relationships.static_encounters_by_header.get(header.header_id, ())
            ),
            connections=tuple(
                relationships.connections_by_header.get(header.header_id, ())
            ),
            items=tuple(items),
            script_awarded_items=tuple(
                relationships.script_awarded_items_by_header.get(header.header_id, ())
            ),
            shops=tuple(shops),
            npc_trades=tuple(
                relationships.npc_trades_by_header.get(header.header_id, ())
            ),
        ).to_dict(),
        unsupported_shop_selectors,
    )


def _read_overworld_data(source: _ArchiveLocationSource, header: Any) -> bytes | None:
    overworld_file_id = header.overworld_file_id
    if (
        overworld_file_id >= len(source.overworld_objects.members)
        or overworld_file_id in source.unused_overworld_members
    ):
        return None
    return source.overworld_objects.read(overworld_file_id)


def _extract_gen5_field_items(
    engine: Any,
    overworld_data: bytes,
    catalogs: _ArchiveLocationCatalogs,
    *,
    visible_item_ids: tuple[int | None, ...],
    hidden_item_ids: tuple[int | None, ...],
) -> list[LocationItem]:
    items = []
    for npc in engine.parse_overworld_npcs(overworld_data):
        item_id = engine.resolve_visible_item_id(
            npc, item_count=catalogs.item_count, item_ids=visible_item_ids
        )
        if item_id is None or item_id not in catalogs.item_names_by_id:
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=catalogs.item_names_by_id[item_id],
                kind="visible",
                event_index=npc.index,
                x=npc.x,
                z=npc.y,
                y=npc.z,
                hidden_flag=None,
            )
        )
    for furniture in engine.parse_overworld_furniture(overworld_data):
        item_id = engine.resolve_hidden_item_id(
            furniture, item_count=catalogs.item_count, item_ids=hidden_item_ids
        )
        if item_id is None or item_id not in catalogs.item_names_by_id:
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=catalogs.item_names_by_id[item_id],
                kind="hidden",
                event_index=furniture.index,
                x=furniture.x,
                z=furniture.y,
                y=furniture.z,
                hidden_flag=None,
            )
        )
    return items


def _extract_gen5_script_shops(
    source: _ArchiveLocationSource,
    catalogs: _ArchiveLocationCatalogs,
    script_file_id: int,
) -> tuple[list[LocationShop], set[str], list[int]]:
    shops = []
    seen_vendor_ids: set[str] = set()
    unsupported_shop_selectors = []
    if script_file_id >= len(source.scripts.members):
        return shops, seen_vendor_ids, unsupported_shop_selectors

    script = source.scripts.read(script_file_id)
    seen_dispatches = set()
    for function_offset in source.engine.parse_function_offsets(script):
        dispatch = source.engine.parse_shop_dispatch(script, function_offset)
        if dispatch is None:
            continue
        dispatch_key = (dispatch.selector_id, dispatch.command_offset)
        if dispatch_key in seen_dispatches:
            continue
        seen_dispatches.add(dispatch_key)
        inventory_id = source.engine.SHOP_SELECTOR_TO_INVENTORY_ID.get(
            dispatch.selector_id
        )
        if inventory_id is not None:
            catalog_shop = catalogs.shops_by_id.get(inventory_id)
            if catalog_shop is not None:
                shops.append(
                    _build_gen5_catalog_shop(
                        catalog_shop,
                        catalogs.item_prices_by_id,
                        inventory_id=inventory_id,
                        script_file_id=script_file_id,
                        dispatch=dispatch,
                    )
                )
            continue

        special_vendor = source.engine.resolve_special_vendor(dispatch.selector_id)
        if special_vendor is not None:
            if (
                special_vendor.vendor_id is None
                or special_vendor.vendor_id not in seen_vendor_ids
            ):
                shops.append(
                    _build_gen5_special_vendor_shop(
                        special_vendor,
                        catalogs.item_names_by_id,
                        script_file_id=script_file_id,
                        command_offset=dispatch.command_offset,
                        selector_id=dispatch.selector_id,
                        mode=dispatch.mode,
                    )
                )
                if special_vendor.vendor_id is not None:
                    seen_vendor_ids.add(special_vendor.vendor_id)
            continue
        if dispatch.selector_id != source.engine.STANDARD_SHOP_SELECTOR:
            unsupported_shop_selectors.append(dispatch.selector_id)
            continue
        shops.append(
            LocationShop(
                kind="common",
                currency="money",
                inventory_id=dispatch.selector_id,
                script_file_id=script_file_id,
                command_offset=dispatch.command_offset,
                items=(),
                name="Standard Poké Mart",
                is_main_game=True,
                selector_id=dispatch.selector_id,
                mode=dispatch.mode,
                dynamic=True,
                inventory_source="runtime",
                availability="Stock changes with badge progression.",
            )
        )
    return shops, seen_vendor_ids, unsupported_shop_selectors


def _build_gen5_catalog_shop(
    catalog_shop: dict[str, Any],
    item_prices_by_id: dict[int, int | None],
    *,
    inventory_id: int,
    script_file_id: int,
    dispatch: Any,
) -> LocationShop:
    return LocationShop(
        kind=catalog_shop["kind"],
        currency="money",
        inventory_id=inventory_id,
        script_file_id=script_file_id,
        command_offset=dispatch.command_offset,
        items=tuple(
            LocationShopItem(
                item_id=item["item_id"],
                name=item["name"],
                price=item_prices_by_id.get(item["item_id"]),
                required_badges=None,
            )
            for item in catalog_shop["items"]
        ),
        name=catalog_shop["name"],
        is_main_game=catalog_shop["is_main_game"],
        selector_id=dispatch.selector_id,
        mode=dispatch.mode,
        inventory_source="rom-catalog",
    )


def _extract_gen5_location_vendors(
    engine: Any,
    header_id: int,
    item_names_by_id: dict[int, str],
    script_file_id: int,
    seen_vendor_ids: set[str],
) -> list[LocationShop]:
    resolve_location_vendors = getattr(engine, "resolve_location_special_vendors", None)
    if resolve_location_vendors is None:
        return []

    shops = []
    for special_vendor in resolve_location_vendors(header_id):
        if (
            special_vendor.vendor_id is not None
            and special_vendor.vendor_id in seen_vendor_ids
        ):
            continue
        shops.append(
            _build_gen5_special_vendor_shop(
                special_vendor,
                item_names_by_id,
                script_file_id=script_file_id,
                command_offset=-1,
            )
        )
        if special_vendor.vendor_id is not None:
            seen_vendor_ids.add(special_vendor.vendor_id)
    return shops


def _extract_gen5_location_warps(
    source: _ArchiveLocationSource,
    overworld_data: bytes | None,
    headers_by_id: dict[int, Any],
) -> list[LocationWarp]:
    if overworld_data is None:
        return []

    warps = []
    for warp in source.engine.parse_overworld_warps(overworld_data):
        if warp.destination_header_id not in headers_by_id:
            warps.append(
                LocationWarp(
                    index=warp.index,
                    x=warp.x,
                    z=warp.z,
                    destination_header_id=None,
                    destination_warp_id=None,
                    destination_name=None,
                    destination_section_name=None,
                    destination_internal_name=None,
                    destination_warp_exists=None,
                    dynamic=True,
                )
            )
            continue
        destination = headers_by_id[warp.destination_header_id]
        destination_section_name, _ = resolve_location_section(
            source.profile,
            header_id=destination.header_id,
            internal_name=None,
        )
        destination_warp_count = len(
            source.engine.parse_overworld_warps(
                _read_overworld_data(source, destination) or b""
            )
        )
        destination_indexed = getattr(source.engine, "WARP_DESTINATION_INDEXED", True)
        warps.append(
            LocationWarp(
                index=warp.index,
                x=warp.x,
                z=warp.z,
                destination_header_id=destination.header_id,
                destination_warp_id=(
                    warp.destination_warp_id if destination_indexed else None
                ),
                destination_name=destination.name,
                destination_section_name=destination_section_name,
                destination_internal_name=f"map_{destination.header_id}",
                destination_warp_exists=(
                    0 <= warp.destination_warp_id < destination_warp_count
                    if destination_indexed
                    else None
                ),
                dynamic=False,
            )
        )
    return warps


def _build_archive_location_envelope(
    source: _ArchiveLocationSource,
    records: list[dict[str, Any]],
    unsupported_shop_selectors: list[int],
) -> dict[str, Any]:
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": source.profile.id,
        "engine": source.profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "encounter_reference_count": sum(
            record["encounter_map_index"] is not None for record in records
        ),
        "trainer_reference_count": sum(len(record["trainers"]) for record in records),
        "warp_reference_count": sum(len(record["warps"]) for record in records),
        "item_reference_count": sum(len(record["items"]) for record in records),
        "script_awarded_item_reference_count": sum(
            len(record["script_awarded_items"]) for record in records
        ),
        "shop_reference_count": sum(len(record["shops"]) for record in records),
        "npc_trade_reference_count": sum(
            len(record["npc_trades"]) for record in records
        ),
        "unsupported_shop_dispatch_count": len(unsupported_shop_selectors),
        "unsupported_shop_selector_ids": sorted(set(unsupported_shop_selectors)),
        "static_encounter_reference_count": sum(
            len(record["static_encounters"]) for record in records
        ),
        "connection_reference_count": sum(
            len(record["connections"]) for record in records
        ),
        "source": {
            "rom_sha256": source.rom_sha256,
            "map_headers_archive": source.map_headers_path,
            "overworld_objects_archive": source.overworld_objects_path,
            "unused_overworld_members": sorted(source.unused_overworld_members),
            "map_matrices_archive": source.map_matrices_path,
            "scripts_archive": source.scripts_path,
            "map_names": {
                "archive": source.messages_path,
                "member": source.map_names_member,
            },
        },
        "records": records,
    }


def _extract_encounter_map_connections(
    engine: Any,
    headers: tuple[Any, ...],
    map_matrices: Any,
) -> dict[int, list[LocationConnection]]:
    """Derive real outdoor connections from each header's matrix grid.

    Each map header's `matrix_id` (see `gen5/bw/locations.py`'s
    `_MATRIX_ID_OFFSET` docstring) selects a grid of real header IDs from
    `layout.map_matrices`; adjacent grid cells are real, geographically
    adjacent maps. A cell value of -1 means "no map there" (verified: real
    grids are ragged rectangles, not fully packed). Mirrors Gen IV's own
    `extract_event_map_connections` algorithm, adapted to the differently-
    shaped `Gen5MapMatrix` (no separate location-name-id indirection --
    `EncounterMapLocation.name` is already the display name).
    """
    headers_by_id = {header.header_id: header for header in headers}
    directions: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    matrix_ids = sorted({header.matrix_id for header in headers})
    parsed_matrices: dict[int, Any] = {}
    for matrix_id in matrix_ids:
        if matrix_id >= len(map_matrices.members):
            raise InvalidRomError(f"Map header references missing matrix {matrix_id}")
        parsed_matrices[matrix_id] = engine.parse_map_matrix(
            map_matrices.read(matrix_id), matrix_id=matrix_id
        )

    for matrix in parsed_matrices.values():
        if matrix.header_ids is None:
            continue
        for index, source in enumerate(matrix.header_ids):
            if source < 0 or source not in headers_by_id:
                continue
            x = index % matrix.width
            y = index // matrix.width
            for offset, forward, reverse in (
                (1, "east", "west"),
                (matrix.width, "south", "north"),
            ):
                if (forward == "east" and x + 1 >= matrix.width) or (
                    forward == "south" and y + 1 >= matrix.height
                ):
                    continue
                destination = matrix.header_ids[index + offset]
                if destination < 0 or destination == source:
                    continue
                if destination not in headers_by_id:
                    continue
                directions[source][destination].add(forward)
                directions[destination][source].add(reverse)

    result: dict[int, list[LocationConnection]] = {}
    direction_order = {"north": 0, "east": 1, "south": 2, "west": 3}
    for source, destinations in directions.items():
        result[source] = []
        for destination_id, values in sorted(destinations.items()):
            destination = headers_by_id[destination_id]
            result[source].append(
                LocationConnection(
                    destination_header_id=destination_id,
                    destination_name=destination.name,
                    destination_internal_name=f"map_{destination_id}",
                    directions=tuple(sorted(values, key=direction_order.__getitem__)),
                )
            )
    return result


def _resolve_gen5_script_locations(
    engine: Any,
    headers: tuple[Any, ...],
    script_file_ids: tuple[int, ...],
    scripts: Any,
    overworld_objects: Any,
    *,
    unused_overworld_members: frozenset[int] = frozenset(),
) -> dict[int, tuple[int, ...]]:
    """Map dedicated and common script members to every proven map caller."""
    member_count = len(scripts.members)
    owners: dict[int, set[int]] = defaultdict(set)
    for header in headers:
        owners[script_file_ids[header.header_id]].add(header.header_id)
        if (
            header.overworld_file_id >= len(overworld_objects.members)
            or header.overworld_file_id in unused_overworld_members
        ):
            continue
        overworld = overworld_objects.read(header.overworld_file_id)
        references = [npc.script_used for npc in engine.parse_overworld_npcs(overworld)]
        references.extend(
            furniture.script_used
            for furniture in engine.parse_overworld_furniture(overworld)
        )
        for reference in references:
            member = engine.resolve_common_script_member(
                reference, member_count=member_count
            )
            if member is not None:
                owners[member].add(header.header_id)

    return {
        member: tuple(sorted(header_ids))
        for member, header_ids in owners.items()
        if header_ids
    }


def _extract_gen5_script_awarded_items(
    engine: Any,
    scripts: Any,
    script_headers: dict[int, tuple[int, ...]],
    item_dataset: dict[str, Any] | None,
) -> dict[int, list[LocationScriptAwardedItem]]:
    item_names = {
        record["item_id"]: record["name"]
        for record in (item_dataset or {}).get("records", ())
    }
    if not item_names:
        return {}
    item_count = max(item_names) + 1
    references: dict[int, list[LocationScriptAwardedItem]] = defaultdict(list)
    seen: set[tuple[int, int, int]] = set()
    for member, header_ids in script_headers.items():
        for award in engine.find_script_awarded_items(
            scripts.read(member), item_count=item_count
        ):
            if award.item_id not in item_names:
                continue
            for header_id in header_ids:
                identity = (header_id, member, award.command_offset)
                if identity in seen:
                    continue
                seen.add(identity)
                references[header_id].append(
                    LocationScriptAwardedItem(
                        item_id=award.item_id,
                        name=item_names[award.item_id],
                        quantity=award.quantity,
                        script_file_id=member,
                        command_offset=award.command_offset,
                        command=award.command,
                    )
                )
    for values in references.values():
        values.sort(key=lambda item: (item.script_file_id, item.command_offset))
    return references


def _extract_gen5_npc_trade_references(
    engine: Any,
    profile: Any,
    messages: Any,
    map_header_data: bytes,
    scripts: Any,
    script_headers: dict[int, tuple[int, ...]],
    trade_dataset: dict[str, Any] | None,
    item_dataset: dict[str, Any] | None,
) -> dict[int, list[dict[str, Any]]]:
    if trade_dataset is None:
        return {}
    records_by_id = {
        record["trade_id"]: record for record in trade_dataset.get("records", ())
    }
    if not records_by_id:
        return {}
    pokemon_names = engine.parse_english_message_archive(
        messages.read(profile.parameters["pokemon_names_member"])
    )
    item_names = {
        record["item_id"]: record["name"]
        for record in (item_dataset or {}).get("records", ())
    }
    references: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()

    def add(trade_id: int, header_id: int, member: int, offset: int) -> None:
        record = records_by_id.get(trade_id)
        identity = (trade_id, header_id)
        if record is None or identity in seen:
            return
        seen.add(identity)
        held_item_id = record.get("held_item_id")
        references[header_id].append(
            {
                **record,
                "requested_species_name": pokemon_names[record["requested_species_id"]],
                "offered_species_name": pokemon_names[record["offered_species_id"]],
                "held_item_name": item_names.get(held_item_id),
                "script_file_id": member,
                "command_offset": offset,
            }
        )

    trade_count = max(records_by_id) + 1
    for member, header_ids in script_headers.items():
        script = scripts.read(member)
        for function_offset in engine.parse_function_offsets(script):
            instructions = tuple(
                engine.disassemble_function(script, function_offset).values()
            )
            assignments: dict[int, set[int]] = defaultdict(set)
            for instruction in instructions:
                if instruction.name in {"WorkSet", "WorkSetConst"}:
                    assignments[instruction.params[0]].add(instruction.params[1])
            for instruction in instructions:
                if instruction.name != "FieldTradeStart":
                    continue
                operand = instruction.params[0]
                candidates = (
                    {operand}
                    if 0 <= operand < trade_count
                    else assignments.get(operand, set())
                )
                for trade_id in candidates:
                    if trade_id not in records_by_id:
                        continue
                    for header_id in header_ids:
                        add(trade_id, header_id, member, instruction.offset)

    text_mapping = getattr(engine, "NPC_TRADE_TEXT_MEMBER_BY_ID", {})
    if text_mapping:
        text_file_ids = engine.parse_map_header_text_files(map_header_data)
        headers_by_text: dict[int, list[int]] = defaultdict(list)
        for header_id, text_file_id in enumerate(text_file_ids):
            headers_by_text[text_file_id].append(header_id)
        for trade_id, text_file_id in text_mapping.items():
            for header_id in headers_by_text.get(text_file_id, ()):
                add(trade_id, header_id, -1, -1)

    for values in references.values():
        values.sort(key=lambda value: value["trade_id"])
    return references


def _extract_static_encounter_references(
    engine: Any,
    profile: Any,
    messages: Any,
    script_headers: dict[int, tuple[int, ...]],
    static_encounter_dataset: dict[str, Any] | None,
) -> dict[int, list[LocationStaticEncounter]]:
    """Resolve static (gift/single) Pokémon encounters to a real map header.

    Each fact is a `[script-file, byte-offset]` pair into `layout.scripts`
    (see `pipeline/extraction/static_encounters.py`); this cross-references the same
    script file against each map header's own dedicated script file (the
    same field §4's trainer-battle-trigger work decoded) rather than
    guessing. Dedicated scripts resolve through map headers; secondary/common
    scripts resolve through proven overworld references. The latter includes
    the museum's shared fossil-revival script.
    """
    if static_encounter_dataset is None:
        return {}
    pokemon_names_member = profile.parameters.get("pokemon_names_member")
    if pokemon_names_member is None:
        return {}
    pokemon_names = engine.parse_english_message_archive(
        messages.read(pokemon_names_member)
    )
    references: dict[int, list[LocationStaticEncounter]] = defaultdict(list)
    for record in static_encounter_dataset["records"]:
        provenance = record.get("provenance", {})
        species_file = provenance.get("member")
        species_offset = record.get("command_offset")
        if not isinstance(species_file, int) or not isinstance(species_offset, int):
            continue
        header_ids = script_headers.get(species_file, ())
        if not header_ids:
            continue
        if record["level"] is None:
            continue
        for header_id in header_ids:
            references[header_id].append(
                LocationStaticEncounter(
                    species_id=record["species_id"],
                    name=pokemon_names[record["species_id"]],
                    level=record["level"],
                    command=record.get("command") or "StaticPokemon",
                    script_file_id=species_file,
                    command_offset=species_offset,
                )
            )
    for values in references.values():
        values.sort(key=lambda item: (item.name, item.level))
    return references
