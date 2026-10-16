from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.archive_encounter_map_source import (
    ArchiveLocationCatalogs,
    ArchiveLocationSource,
    build_archive_location_catalogs,
    load_archive_location_source,
)
from romwiki.pipeline.extraction.locations.archive_location_shops import (
    extract_location_vendors,
    extract_script_shops,
)
from romwiki.pipeline.extraction.locations.archive_script_references import (
    extract_npc_trade_references,
    extract_script_awarded_items,
    extract_static_encounter_references,
    resolve_script_locations,
)
from romwiki.pipeline.extraction.locations.helpers import extract_trainer_references
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
)
from romwiki.schema import (
    LocationConnection,
    LocationItem,
    LocationScriptAwardedItem,
    LocationShop,
    LocationStaticEncounter,
    LocationWarp,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class _ArchiveLocationRelationships:
    trainers_by_header: dict[int, list[Any]]
    static_encounters_by_header: dict[int, list[LocationStaticEncounter]]
    npc_trades_by_header: dict[int, list[dict[str, Any]]]
    script_awarded_items_by_header: dict[int, list[LocationScriptAwardedItem]]
    connections_by_header: dict[int, list[LocationConnection]]


def extract_archive_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for location extraction")
    source = load_archive_location_source(result)
    relationships = _collect_archive_location_relationships(
        result,
        source,
        trainer_dataset=trainer_dataset,
        static_encounter_dataset=static_encounter_dataset,
        trade_dataset=trade_dataset,
        item_dataset=item_dataset,
    )
    catalogs = build_archive_location_catalogs(item_dataset, mart_dataset)
    records, unsupported_shop_selectors, unresolved_visible_item_count = (
        _build_archive_location_records(source, relationships, catalogs)
    )
    return _build_archive_location_envelope(
        source, records, unsupported_shop_selectors, unresolved_visible_item_count
    )


def _collect_archive_location_relationships(
    result: InspectionResult,
    source: ArchiveLocationSource,
    *,
    trainer_dataset: dict[str, Any] | None,
    static_encounter_dataset: dict[str, Any] | None,
    trade_dataset: dict[str, Any] | None,
    item_dataset: dict[str, Any] | None,
) -> _ArchiveLocationRelationships:
    script_headers = resolve_script_locations(
        source.engine,
        source.headers,
        source.script_file_ids,
        source.scripts,
        source.overworld_objects,
        unused_overworld_members=source.unused_overworld_members,
    )
    return _ArchiveLocationRelationships(
        trainers_by_header=extract_trainer_references(result, trainer_dataset),
        static_encounters_by_header=extract_static_encounter_references(
            source.engine,
            source.profile,
            source.messages,
            script_headers,
            static_encounter_dataset,
        ),
        npc_trades_by_header=extract_npc_trade_references(
            source.engine,
            source.profile,
            source.messages,
            source.map_headers.read(0),
            source.scripts,
            script_headers,
            trade_dataset,
            item_dataset,
        ),
        script_awarded_items_by_header=extract_script_awarded_items(
            source.engine,
            source.scripts,
            script_headers,
            item_dataset,
        ),
        connections_by_header=_extract_encounter_map_connections(
            source.engine, source.headers, source.map_matrices
        ),
    )


def _build_archive_location_records(
    source: ArchiveLocationSource,
    relationships: _ArchiveLocationRelationships,
    catalogs: ArchiveLocationCatalogs,
) -> tuple[list[dict[str, Any]], list[int], int]:
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
    unresolved_visible_item_count = 0
    for header in source.headers:
        record, unsupported_selectors, header_unresolved_count = (
            _build_archive_location_record(
                source,
                relationships,
                catalogs,
                headers_by_id,
                header,
                visible_item_ids,
                hidden_item_ids,
            )
        )
        records.append(record)
        unsupported_shop_selectors.extend(unsupported_selectors)
        unresolved_visible_item_count += header_unresolved_count
    return records, unsupported_shop_selectors, unresolved_visible_item_count


def _build_archive_location_record(
    source: ArchiveLocationSource,
    relationships: _ArchiveLocationRelationships,
    catalogs: ArchiveLocationCatalogs,
    headers_by_id: dict[int, Any],
    header: Any,
    visible_item_ids: tuple[int | None, ...],
    hidden_item_ids: tuple[int | None, ...],
) -> tuple[dict[str, Any], list[int], int]:
    section_name, section_name_source = resolve_location_section(
        source.profile,
        header_id=header.header_id,
        internal_name=None,
    )
    script_file_id = source.script_file_ids[header.header_id]
    overworld_data = _read_overworld_data(source, header)
    items, unresolved_visible_item_count = (
        _extract_field_items(
            source.engine,
            overworld_data,
            catalogs,
            visible_item_ids=visible_item_ids,
            hidden_item_ids=hidden_item_ids,
        )
        if overworld_data is not None
        else ([], 0)
    )
    if overworld_data is None:
        shops: list[LocationShop] = []
        seen_vendor_ids: set[str] = set()
        unsupported_shop_selectors: list[int] = []
    else:
        shops, seen_vendor_ids, unsupported_shop_selectors = extract_script_shops(
            source, catalogs, script_file_id
        )
    shops.extend(
        extract_location_vendors(
            source,
            header.header_id,
            catalogs.item_names_by_id,
            script_file_id,
            seen_vendor_ids,
        )
    )
    warps = _extract_location_warps(source, overworld_data, headers_by_id)
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
        unresolved_visible_item_count,
    )


def _read_overworld_data(source: ArchiveLocationSource, header: Any) -> bytes | None:
    overworld_file_id = header.overworld_file_id
    if (
        overworld_file_id >= len(source.overworld_objects.members)
        or overworld_file_id in source.unused_overworld_members
    ):
        return None
    return source.overworld_objects.read(overworld_file_id)


def _extract_field_items(
    engine: LocationConcern,
    overworld_data: bytes,
    catalogs: ArchiveLocationCatalogs,
    *,
    visible_item_ids: tuple[int | None, ...],
    hidden_item_ids: tuple[int | None, ...],
) -> tuple[list[LocationItem], int]:
    items = []
    unresolved_visible_item_count = 0
    for npc in engine.parse_overworld_npcs(overworld_data):
        item_id = engine.resolve_visible_item_id(
            npc, item_count=catalogs.item_count, item_ids=visible_item_ids
        )
        if item_id is None or item_id not in catalogs.item_names_by_id:
            if engine.is_visible_item_candidate(npc):
                unresolved_visible_item_count += 1
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
    return items, unresolved_visible_item_count


def _extract_location_warps(
    source: ArchiveLocationSource,
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
        destination_indexed = source.engine.WARP_DESTINATION_INDEXED
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
    source: ArchiveLocationSource,
    records: list[dict[str, Any]],
    unsupported_shop_selectors: list[int],
    unresolved_visible_item_count: int,
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
        "unresolved_visible_item_count": unresolved_visible_item_count,
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
    engine: LocationConcern,
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
