from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.location_helpers import extract_trainer_references
from romwiki.pipeline.location_sections import (
    resolve_location_section,
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    LocationConnection,
    LocationItem,
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


def extract_archive_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Each map header's display name, its wild-encounter-table cross-
    # reference, its real trainers, its real warps, its real static
    # (gift/single) PokÃ©mon encounters, its real outdoor connections, and its
    # real field items, and its real script-linked shops.
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
    trainers_by_header = extract_trainer_references(result, trainer_dataset)
    overworld_objects = platform.archive_cls.from_bytes(
        filesystem.read(overworld_objects_path), **field_archive_options
    )
    map_matrices = platform.archive_cls.from_bytes(filesystem.read(map_matrices_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **field_archive_options
    )
    unused_overworld_members = frozenset(
        profile.parameters.get("overworld_objects_unused", ())
    )
    script_headers = _resolve_gen5_script_locations(
        engine,
        headers,
        script_file_ids,
        scripts,
        overworld_objects,
        unused_overworld_members=unused_overworld_members,
    )
    static_encounters_by_header = _extract_static_encounter_references(
        engine, profile, messages, script_headers, static_encounter_dataset
    )
    npc_trades_by_header = _extract_gen5_npc_trade_references(
        engine,
        profile,
        messages,
        map_headers.read(0),
        scripts,
        script_headers,
        trade_dataset,
        item_dataset,
    )
    connections_by_header = _extract_encounter_map_connections(
        engine, headers, map_matrices
    )
    item_names_by_id = {
        record["item_id"]: record["name"]
        for record in (item_dataset or {}).get("records", ())
    }
    item_prices_by_id = {
        record["item_id"]: record.get("price")
        for record in (item_dataset or {}).get("records", ())
    }
    shops_by_id = {
        record["shop_id"]: record for record in (mart_dataset or {}).get("records", ())
    }
    item_count = max(item_names_by_id, default=-1) + 1
    headers_by_id = {header.header_id: header for header in headers}
    records = []
    unsupported_shop_selectors = []
    for header in headers:
        section_name, section_name_source = resolve_location_section(
            profile,
            header_id=header.header_id,
            internal_name=header.internal_name,
        )
        items = []
        shops = []
        seen_vendor_ids: set[str] = set()
        script_file_id = script_file_ids[header.header_id]
        if (
            header.header_id < len(overworld_objects.members)
            and header.header_id not in unused_overworld_members
        ):
            overworld_data = overworld_objects.read(header.header_id)
            npcs = engine.parse_overworld_npcs(overworld_data)
            for npc in npcs:
                item_id = engine.resolve_visible_item_id(npc, item_count=item_count)
                if item_id is None or item_id not in item_names_by_id:
                    continue
                items.append(
                    LocationItem(
                        item_id=item_id,
                        name=item_names_by_id[item_id],
                        kind="visible",
                        event_index=npc.index,
                        x=npc.x,
                        z=npc.y,
                        y=npc.z,
                        hidden_flag=None,
                    )
                )
            if script_file_id < len(scripts.members):
                script = scripts.read(script_file_id)
                function_offsets = engine.parse_function_offsets(script)
                seen_dispatches = set()
                for function_offset in function_offsets:
                    dispatch = engine.parse_shop_dispatch(script, function_offset)
                    if dispatch is None:
                        continue
                    dispatch_key = (dispatch.selector_id, dispatch.command_offset)
                    if dispatch_key in seen_dispatches:
                        continue
                    seen_dispatches.add(dispatch_key)
                    inventory_id = engine.SHOP_SELECTOR_TO_INVENTORY_ID.get(
                        dispatch.selector_id
                    )
                    if inventory_id is None:
                        special_vendor = engine.resolve_special_vendor(
                            dispatch.selector_id
                        )
                        if special_vendor is not None:
                            if (
                                special_vendor.vendor_id is None
                                or special_vendor.vendor_id not in seen_vendor_ids
                            ):
                                shops.append(
                                    _build_gen5_special_vendor_shop(
                                        special_vendor,
                                        item_names_by_id,
                                        script_file_id=script_file_id,
                                        command_offset=dispatch.command_offset,
                                        selector_id=dispatch.selector_id,
                                        mode=dispatch.mode,
                                    )
                                )
                                if special_vendor.vendor_id is not None:
                                    seen_vendor_ids.add(special_vendor.vendor_id)
                            continue
                        if dispatch.selector_id != engine.STANDARD_SHOP_SELECTOR:
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
                                availability=("Stock changes with badge progression."),
                            )
                        )
                        continue
                    catalog_shop = shops_by_id.get(inventory_id)
                    if catalog_shop is None:
                        continue
                    shops.append(
                        LocationShop(
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
                    )
            for furniture in engine.parse_overworld_furniture(overworld_data):
                item_id = engine.resolve_hidden_item_id(
                    furniture, item_count=item_count
                )
                if item_id is None or item_id not in item_names_by_id:
                    continue
                items.append(
                    LocationItem(
                        item_id=item_id,
                        name=item_names_by_id[item_id],
                        kind="hidden",
                        event_index=furniture.index,
                        x=furniture.x,
                        z=furniture.y,
                        y=furniture.z,
                        hidden_flag=None,
                    )
                )
        resolve_location_vendors = getattr(
            engine, "resolve_location_special_vendors", None
        )
        if resolve_location_vendors is not None:
            for special_vendor in resolve_location_vendors(header.header_id):
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
        warps = []
        if (
            header.header_id < len(overworld_objects.members)
            and header.header_id not in unused_overworld_members
        ):
            raw_warps = engine.parse_overworld_warps(
                overworld_objects.read(header.header_id)
            )
            for warp in raw_warps:
                if warp.destination_header_id not in headers_by_id:
                    warps.append(
                        LocationWarp(
                            index=warp.index,
                            x=warp.x,
                            z=warp.z,
                            destination_header_id=None,
                            destination_warp_id=None,
                            destination_name=None,
                            destination_internal_name=None,
                            destination_warp_exists=None,
                            dynamic=True,
                        )
                    )
                    continue
                destination = headers_by_id[warp.destination_header_id]
                destination_warp_count = len(
                    engine.parse_overworld_warps(
                        overworld_objects.read(destination.header_id)
                        if destination.header_id not in unused_overworld_members
                        else b""
                    )
                )
                warps.append(
                    LocationWarp(
                        index=warp.index,
                        x=warp.x,
                        z=warp.z,
                        destination_header_id=destination.header_id,
                        destination_warp_id=(
                            warp.destination_warp_id
                            if getattr(engine, "WARP_DESTINATION_INDEXED", True)
                            else None
                        ),
                        destination_name=destination.name,
                        destination_internal_name=f"map_{destination.header_id}",
                        destination_warp_exists=(
                            0 <= warp.destination_warp_id < destination_warp_count
                            if getattr(engine, "WARP_DESTINATION_INDEXED", True)
                            else None
                        ),
                        dynamic=False,
                    )
                )
        records.append(
            replace(
                header,
                section_name=section_name,
                section_name_source=section_name_source,
                trainers=tuple(trainers_by_header.get(header.header_id, ())),
                warps=tuple(warps),
                static_encounters=tuple(
                    static_encounters_by_header.get(header.header_id, ())
                ),
                connections=tuple(connections_by_header.get(header.header_id, ())),
                items=tuple(items),
                shops=tuple(shops),
                npc_trades=tuple(npc_trades_by_header.get(header.header_id, ())),
            ).to_dict()
        )
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "encounter_reference_count": sum(
            record["encounter_map_index"] is not None for record in records
        ),
        "trainer_reference_count": sum(len(record["trainers"]) for record in records),
        "warp_reference_count": sum(len(record["warps"]) for record in records),
        "item_reference_count": sum(len(record["items"]) for record in records),
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
            "rom_sha256": result.image.hashes.sha256,
            "map_headers_archive": map_headers_path,
            "overworld_objects_archive": overworld_objects_path,
            "unused_overworld_members": sorted(unused_overworld_members),
            "map_matrices_archive": map_matrices_path,
            "scripts_archive": scripts_path,
            "map_names": {"archive": messages_path, "member": map_names_member},
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
            header.header_id >= len(overworld_objects.members)
            or header.header_id in unused_overworld_members
        ):
            continue
        overworld = overworld_objects.read(header.header_id)
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
    (see `pipeline/static_encounters.py`); this cross-references the same
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
