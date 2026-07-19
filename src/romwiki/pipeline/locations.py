from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    MAP_HEADER_SIZE,
    Gen4CommonMartItem,
    Gen4MapEvents,
    Gen4WarpEvent,
    PlatinumMapHeader,
    parse_english_message_archive,
    parse_map_matrix,
    parse_map_events,
    parse_common_mart_inventory,
    parse_decoration_price_table,
    parse_egg_gift_command,
    parse_frontier_price_table,
    parse_item_price,
    parse_mart_commands,
    parse_pokemon_gift_commands,
    parse_seal_price_table,
    parse_static_encounter_commands,
    parse_platinum_map_headers,
    parse_specialty_mart_inventories,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.trainers import extract_trainer_dataset
from romwiki.platforms.nds import (
    NarcArchive,
    NintendoDSFileSystem,
    read_arm9_overlay,
)
from romwiki.schema import (
    Gen4Location,
    LocationConnection,
    LocationItem,
    LocationPokemonGift,
    LocationStaticEncounter,
    LocationShop,
    LocationShopItem,
    LocationTrainerReference,
    LocationWarp,
)


_ITEM_BALL_GRAPHICS_ID = 87
_VISIBLE_ITEM_SCRIPT_BASE = 7000
_HIDDEN_ITEM_EVENT_TYPE = 2
_HIDDEN_ITEM_SCRIPT_BASE = 8000


def extract_location_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for location extraction")
    profile = result.match.profile
    try:
        events_path = profile.layout["events"]
        matrices_path = profile.layout["map_matrices"]
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        scripts_path = profile.layout["scripts"]
        item_data_path = profile.layout["item_data"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        item_names_member = profile.parameters["item_names_member"]
        pokemon_names_member = profile.parameters["pokemon_names_member"]
        decoration_names_member = profile.parameters["decoration_names_member"]
        decoration_name_count = profile.parameters["decoration_name_count"]
        seal_names_member = profile.parameters["seal_names_member"]
        null_event_id = profile.parameters["null_event_id"]
        null_encounter_id = profile.parameters["null_encounter_id"]
        dynamic_warp_header_id = profile.parameters["dynamic_warp_header_id"]
        dynamic_warp_id = profile.parameters["dynamic_warp_id"]
        matrix_void_header_ids = frozenset(
            profile.parameters["matrix_void_header_ids"]
        )
        common_mart_inventory_offset = profile.parameters[
            "common_mart_inventory_offset"
        ]
        specialty_mart_pointer_table_offset = profile.parameters[
            "specialty_mart_pointer_table_offset"
        ]
        specialty_mart_inventory_count = profile.parameters[
            "specialty_mart_inventory_count"
        ]
        decoration_mart_inventory_start = profile.parameters[
            "decoration_mart_inventory_start"
        ]
        decoration_mart_inventory_count = profile.parameters[
            "decoration_mart_inventory_count"
        ]
        decoration_price_table_offset = profile.parameters[
            "decoration_price_table_offset"
        ]
        seal_mart_inventory_start = profile.parameters["seal_mart_inventory_start"]
        seal_mart_inventory_count = profile.parameters["seal_mart_inventory_count"]
        seal_price_table_offset = profile.parameters["seal_price_table_offset"]
        frontier_mart_inventory_count = profile.parameters[
            "frontier_mart_inventory_count"
        ]
        frontier_price_overlay_id = profile.parameters["frontier_price_overlay_id"]
        frontier_price_table_offset = profile.parameters[
            "frontier_price_table_offset"
        ]
        frontier_price_record_count = profile.parameters[
            "frontier_price_record_count"
        ]
        egg_gift_metadata = profile.parameters["egg_gifts"]
        arm9_load_address = profile.parameters["arm9_load_address"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    with result.image.path.open("rb") as stream:
        stream.seek(result.image.header.arm9_offset)
        arm9_data = stream.read(result.image.header.arm9_size)
    header_data = arm9_data[table_offset : table_offset + count * MAP_HEADER_SIZE]
    headers = parse_platinum_map_headers(
        header_data, filesystem.read(map_names_path), count=count
    )
    messages = NarcArchive.from_bytes(filesystem.read(messages_path))
    location_names = parse_english_message_archive(
        messages.read(location_names_member)
    )
    item_names = parse_english_message_archive(messages.read(item_names_member))
    pokemon_names = parse_english_message_archive(messages.read(pokemon_names_member))
    decoration_names = parse_english_message_archive(
        messages.read(decoration_names_member), limit=decoration_name_count
    )
    seal_names = parse_english_message_archive(messages.read(seal_names_member))
    decoration_prices = parse_decoration_price_table(
        arm9_data,
        offset=decoration_price_table_offset,
        decoration_count=len(decoration_names),
    )
    seal_prices = parse_seal_price_table(
        arm9_data, offset=seal_price_table_offset, seal_count=len(seal_names)
    )
    _, frontier_overlay = read_arm9_overlay(
        result.image, frontier_price_overlay_id
    )
    frontier_prices = parse_frontier_price_table(
        frontier_overlay,
        offset=frontier_price_table_offset,
        record_count=frontier_price_record_count,
    )
    item_data = NarcArchive.from_bytes(filesystem.read(item_data_path))
    item_prices = tuple(
        parse_item_price(item_data.read(index))
        for index in range(len(item_data.members))
    )
    common_mart_items = parse_common_mart_inventory(
        arm9_data, offset=common_mart_inventory_offset, item_count=len(item_names)
    )
    specialty_mart_inventories = parse_specialty_mart_inventories(
        arm9_data,
        pointer_table_offset=specialty_mart_pointer_table_offset,
        inventory_count=specialty_mart_inventory_count,
        load_address=arm9_load_address,
        item_count=len(item_names),
    )
    scripts = NarcArchive.from_bytes(
        filesystem.read(scripts_path), allow_truncated=True
    )
    events = NarcArchive.from_bytes(filesystem.read(events_path))
    matrices = NarcArchive.from_bytes(filesystem.read(matrices_path))
    shops_by_script: dict[int, tuple[LocationShop, ...]] = {}
    gifts_by_script: dict[int, tuple[LocationPokemonGift, ...]] = {}
    static_encounters_by_script: dict[int, tuple[LocationStaticEncounter, ...]] = {}
    egg_gifts_by_script: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for metadata in egg_gift_metadata:
        egg_gifts_by_script[metadata["script_member"]].append(metadata)

    events_by_id: dict[int, Gen4MapEvents] = {}
    items_by_event: dict[int, tuple[LocationItem, ...]] = {}
    raw_warps_by_header: dict[int, tuple[Gen4WarpEvent, ...]] = {}
    raw_items_by_header: dict[int, tuple[LocationItem, ...]] = {}
    for header in headers:
        if header.location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing location name "
                f"{header.location_name_id}"
            )
        if header.event_file_id == null_event_id:
            raw_warps_by_header[header.header_id] = ()
            raw_items_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in events_by_id:
            events_by_id[header.event_file_id] = parse_map_events(
                events.read(header.event_file_id), event_file_id=header.event_file_id
            )
            items_by_event[header.event_file_id] = _extract_location_items(
                events_by_id[header.event_file_id], item_names
            )
        raw_warps_by_header[header.header_id] = events_by_id[
            header.event_file_id
        ].warps
        raw_items_by_header[header.header_id] = items_by_event[header.event_file_id]

    connections = _extract_matrix_connections(
        headers, matrices, location_names, matrix_void_header_ids
    )
    trainers = _extract_trainer_references(result)
    records = []
    for header in headers:
        if header.script_file_id >= len(scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{header.script_file_id}"
            )
        if header.script_file_id not in shops_by_script:
            shops_by_script[header.script_file_id] = _extract_location_shops(
                scripts.read(header.script_file_id),
                script_file_id=header.script_file_id,
                common_items=common_mart_items,
                specialty_inventories=specialty_mart_inventories,
                decoration_inventory_start=decoration_mart_inventory_start,
                decoration_inventory_count=decoration_mart_inventory_count,
                seal_inventory_start=seal_mart_inventory_start,
                seal_inventory_count=seal_mart_inventory_count,
                frontier_inventory_count=frontier_mart_inventory_count,
                item_names=item_names,
                item_prices=item_prices,
                decoration_names=decoration_names,
                seal_names=seal_names,
                decoration_prices=decoration_prices,
                seal_prices=seal_prices,
                frontier_prices=frontier_prices,
            )
        if header.script_file_id not in gifts_by_script:
            gifts_by_script[header.script_file_id] = _extract_location_pokemon_gifts(
                scripts.read(header.script_file_id),
                script_file_id=header.script_file_id,
                pokemon_names=pokemon_names,
                item_names=item_names,
                egg_gift_metadata=egg_gifts_by_script.get(
                    header.script_file_id, []
                ),
            )
        if header.script_file_id not in static_encounters_by_script:
            static_encounters_by_script[header.script_file_id] = (
                _extract_location_static_encounters(
                    scripts.read(header.script_file_id),
                    script_file_id=header.script_file_id,
                    pokemon_names=pokemon_names,
                )
            )
        warps = []
        for warp in raw_warps_by_header[header.header_id]:
            dynamic = (
                warp.destination_header_id == dynamic_warp_header_id
                and warp.destination_warp_id == dynamic_warp_id
            )
            if dynamic:
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
            if not 0 <= warp.destination_header_id < len(headers):
                raise InvalidRomError(
                    f"Map header {header.header_id} warp {warp.index} references "
                    f"missing header {warp.destination_header_id}"
                )
            destination = headers[warp.destination_header_id]
            destination_warps = raw_warps_by_header[destination.header_id]
            warps.append(
                LocationWarp(
                    index=warp.index,
                    x=warp.x,
                    z=warp.z,
                    destination_header_id=destination.header_id,
                    destination_warp_id=warp.destination_warp_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_internal_name=destination.internal_name,
                    destination_warp_exists=(
                        warp.destination_warp_id < len(destination_warps)
                    ),
                    dynamic=False,
                )
            )
        records.append(
            Gen4Location(
                header_id=header.header_id,
                internal_name=header.internal_name,
                location_name_id=header.location_name_id,
                name=location_names[header.location_name_id],
                matrix_id=header.matrix_id,
                event_file_id=(
                    None
                    if header.event_file_id == null_event_id
                    else header.event_file_id
                ),
                encounter_id=(
                    None
                    if header.encounter_id == null_encounter_id
                    else header.encounter_id
                ),
                warps=tuple(warps),
                connections=tuple(connections.get(header.header_id, ())),
                trainers=tuple(trainers.get(header.header_id, ())),
                items=raw_items_by_header[header.header_id],
                shops=shops_by_script[header.script_file_id],
                pokemon_gifts=gifts_by_script[header.script_file_id],
                static_encounters=static_encounters_by_script[
                    header.script_file_id
                ],
            ).to_dict()
        )
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "locations",
        "record_count": len(records),
        "warp_count": sum(len(record["warps"]) for record in records),
        "dynamic_warp_count": sum(
            warp["dynamic"] for record in records for warp in record["warps"]
        ),
        "missing_destination_warp_count": sum(
            warp["destination_warp_exists"] is False
            for record in records
            for warp in record["warps"]
        ),
        "connection_count": sum(len(record["connections"]) for record in records),
        "visible_item_count": sum(
            item.kind == "visible"
            for items in items_by_event.values()
            for item in items
        ),
        "hidden_item_count": sum(
            item.kind == "hidden"
            for items in items_by_event.values()
            for item in items
        ),
        "location_item_reference_count": sum(
            len(record["items"]) for record in records
        ),
        "shop_count": sum(len(record["shops"]) for record in records),
        "shop_item_reference_count": sum(
            len(shop["items"])
            for record in records
            for shop in record["shops"]
        ),
        "pokemon_gift_count": sum(
            len(record["pokemon_gifts"]) for record in records
        ),
        "static_encounter_count": sum(
            len(record["static_encounters"]) for record in records
        ),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "events_archive": events_path,
            "map_matrices_archive": matrices_path,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "location_names": {
                "archive": messages_path,
                "member": location_names_member,
            },
            "item_names": {
                "archive": messages_path,
                "member": item_names_member,
            },
            "pokemon_names": {
                "archive": messages_path,
                "member": pokemon_names_member,
            },
            "pokemon_gifts": {
                "scripts_archive": scripts_path,
                "egg_commands": egg_gift_metadata,
            },
            "static_encounters": {
                "scripts_archive": scripts_path,
                "command": "WildBattle",
            },
            "decoration_names": {
                "archive": messages_path,
                "member": decoration_names_member,
                "count": decoration_name_count,
            },
            "seal_names": {
                "archive": messages_path,
                "member": seal_names_member,
            },
            "shops": {
                "scripts_archive": scripts_path,
                "item_data_archive": item_data_path,
                "common_inventory_arm9_offset": common_mart_inventory_offset,
                "specialty_pointer_table_arm9_offset": (
                    specialty_mart_pointer_table_offset
                ),
                "decoration_price_table_arm9_offset": (
                    decoration_price_table_offset
                ),
                "seal_price_table_arm9_offset": seal_price_table_offset,
                "frontier_price_table": {
                    "overlay_id": frontier_price_overlay_id,
                    "offset": frontier_price_table_offset,
                    "record_count": frontier_price_record_count,
                },
            },
        },
        "records": records,
    }


def _extract_location_shops(
    script: bytes,
    *,
    script_file_id: int,
    common_items: tuple[Gen4CommonMartItem, ...],
    specialty_inventories: tuple[tuple[int, ...], ...],
    decoration_inventory_start: int,
    decoration_inventory_count: int,
    seal_inventory_start: int,
    seal_inventory_count: int,
    frontier_inventory_count: int,
    item_names: tuple[str, ...],
    item_prices: tuple[int, ...],
    decoration_names: tuple[str, ...],
    seal_names: tuple[str, ...],
    decoration_prices: tuple[int, ...],
    seal_prices: tuple[int, ...],
    frontier_prices: dict[int, int],
) -> tuple[LocationShop, ...]:
    shops = []
    for command in parse_mart_commands(script):
        price_by_item: dict[int, int] | None = None
        currency = "money"
        if command.kind == "common":
            source_items = (
                (item.item_id, item.required_badges) for item in common_items
            )
            names = item_names
            prices: tuple[int, ...] | None = item_prices
        else:
            inventory_index = command.inventory_id
            names = item_names
            prices = item_prices
            if command.kind == "decoration":
                if command.inventory_id >= decoration_inventory_count:
                    raise InvalidRomError(
                        f"Script {script_file_id} references missing decoration mart "
                        f"{command.inventory_id}"
                    )
                inventory_index += decoration_inventory_start
                names = decoration_names
                prices = decoration_prices
            elif command.kind == "seal":
                if command.inventory_id >= seal_inventory_count:
                    raise InvalidRomError(
                        f"Script {script_file_id} references missing seal mart "
                        f"{command.inventory_id}"
                    )
                inventory_index += seal_inventory_start
                names = seal_names
                prices = seal_prices
            elif command.kind == "frontier":
                if command.inventory_id >= frontier_inventory_count:
                    raise InvalidRomError(
                        f"Script {script_file_id} references missing Battle Frontier "
                        f"mart {command.inventory_id}"
                    )
                names = item_names
                prices = None
                price_by_item = frontier_prices
                currency = "bp"
            if inventory_index >= len(specialty_inventories):
                raise InvalidRomError(
                    f"Script {script_file_id} references missing {command.kind} mart "
                    f"inventory {inventory_index}"
                )
            source_items = (
                (item_id, None)
                for item_id in specialty_inventories[inventory_index]
            )
        source_items = tuple(source_items)
        for item_id, _required_badges in source_items:
            if not 0 < item_id < len(names):
                raise InvalidRomError(
                    f"Script {script_file_id} {command.kind} mart references "
                    f"missing catalog entry {item_id}"
                )
            if price_by_item is not None and item_id not in price_by_item:
                raise InvalidRomError(
                    f"Script {script_file_id} Battle Frontier mart item {item_id} "
                    "has no BP price"
                )
        items = tuple(
            LocationShopItem(
                item_id=item_id,
                name=names[item_id],
                price=(
                    price_by_item[item_id]
                    if price_by_item is not None
                    else (
                        prices[item_id]
                        if prices is not None and item_id < len(prices)
                        else None
                    )
                ),
                required_badges=required_badges,
            )
            for item_id, required_badges in source_items
        )
        shops.append(
            LocationShop(
                kind=command.kind,
                currency=currency,
                inventory_id=command.inventory_id,
                script_file_id=script_file_id,
                command_offset=command.offset,
                items=items,
            )
        )
    return tuple(shops)


def _extract_location_pokemon_gifts(
    script: bytes,
    *,
    script_file_id: int,
    pokemon_names: tuple[str, ...],
    item_names: tuple[str, ...],
    egg_gift_metadata: list[dict[str, Any]],
) -> tuple[LocationPokemonGift, ...]:
    gifts = []
    for command in parse_pokemon_gift_commands(
        script, species_count=len(pokemon_names), item_count=len(item_names)
    ):
        held_item_id = command.held_item_id or None
        gifts.append(
            LocationPokemonGift(
                kind="pokemon",
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=command.level,
                held_item_id=held_item_id,
                held_item_name=(
                    item_names[held_item_id] if held_item_id is not None else None
                ),
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    for metadata in egg_gift_metadata:
        command = parse_egg_gift_command(
            script,
            offset=metadata["command_offset"],
            species_count=len(pokemon_names),
        )
        gifts.append(
            LocationPokemonGift(
                kind="egg",
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=1,
                held_item_id=None,
                held_item_name=None,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(sorted(gifts, key=lambda gift: gift.command_offset))


def _extract_location_static_encounters(
    script: bytes,
    *,
    script_file_id: int,
    pokemon_names: tuple[str, ...],
) -> tuple[LocationStaticEncounter, ...]:
    return tuple(
        LocationStaticEncounter(
            species_id=command.species_id,
            name=pokemon_names[command.species_id],
            level=command.level,
            script_file_id=script_file_id,
            command_offset=command.offset,
        )
        for command in parse_static_encounter_commands(
            script, species_count=len(pokemon_names)
        )
    )


def _extract_location_items(
    events: Gen4MapEvents, item_names: tuple[str, ...]
) -> tuple[LocationItem, ...]:
    items = []
    for event in events.objects:
        item_id = event.script_id - _VISIBLE_ITEM_SCRIPT_BASE
        if event.graphics_id != _ITEM_BALL_GRAPHICS_ID or not 1 <= item_id < len(
            item_names
        ):
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=item_names[item_id],
                kind="visible",
                event_index=event.index,
                x=event.x,
                z=event.z,
                y=event.y,
                hidden_flag=event.hidden_flag,
            )
        )
    for event in events.backgrounds:
        item_id = event.script_id - _HIDDEN_ITEM_SCRIPT_BASE
        if event.event_type != _HIDDEN_ITEM_EVENT_TYPE or not 1 <= item_id < len(
            item_names
        ):
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=item_names[item_id],
                kind="hidden",
                event_index=event.index,
                x=event.x,
                z=event.z,
                y=event.y,
                hidden_flag=None,
            )
        )
    return tuple(items)


def _extract_matrix_connections(
    headers: tuple[PlatinumMapHeader, ...],
    matrices: NarcArchive,
    location_names: tuple[str, ...],
    void_header_ids: frozenset[int],
) -> dict[int, list[LocationConnection]]:
    directions: dict[int, dict[int, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for matrix_id in sorted({header.matrix_id for header in headers}):
        if matrix_id >= len(matrices.members):
            raise InvalidRomError(f"Map header references missing matrix {matrix_id}")
        matrix = parse_map_matrix(matrices.read(matrix_id), matrix_id=matrix_id)
        if matrix.header_ids is None:
            continue
        for index, source in enumerate(matrix.header_ids):
            if source in void_header_ids:
                continue
            if source >= len(headers):
                raise InvalidRomError(
                    f"Map matrix {matrix_id} references missing header {source}"
                )
            x = index % matrix.width
            z = index // matrix.width
            for offset, forward, reverse in (
                (1, "east", "west"),
                (matrix.width, "south", "north"),
            ):
                if (forward == "east" and x + 1 >= matrix.width) or (
                    forward == "south" and z + 1 >= matrix.height
                ):
                    continue
                destination = matrix.header_ids[index + offset]
                if destination == source or destination in void_header_ids:
                    continue
                if destination >= len(headers):
                    raise InvalidRomError(
                        f"Map matrix {matrix_id} references missing header "
                        f"{destination}"
                    )
                directions[source][destination].add(forward)
                directions[destination][source].add(reverse)

    result = {}
    direction_order = {"north": 0, "east": 1, "south": 2, "west": 3}
    for source, destinations in directions.items():
        result[source] = []
        for destination_id, values in sorted(destinations.items()):
            destination = headers[destination_id]
            result[source].append(
                LocationConnection(
                    destination_header_id=destination_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_internal_name=destination.internal_name,
                    directions=tuple(sorted(values, key=direction_order.__getitem__)),
                )
            )
    return result


def _extract_trainer_references(
    result: InspectionResult,
) -> dict[int, list[LocationTrainerReference]]:
    references: dict[int, list[LocationTrainerReference]] = defaultdict(list)
    seen: set[tuple[int, int, str]] = set()
    for trainer in extract_trainer_dataset(result)["records"]:
        for source, locations in (
            ("overworld-object", trainer["locations"]),
            ("map-script", trainer["script_references"]),
        ):
            for location in locations:
                key = (location["header_id"], trainer["trainer_id"], source)
                if key in seen:
                    continue
                seen.add(key)
                references[location["header_id"]].append(
                    LocationTrainerReference(
                        trainer_id=trainer["trainer_id"],
                        name=trainer["name"],
                        class_name=trainer["class_name"],
                        source=source,
                    )
                )
    for values in references.values():
        values.sort(key=lambda item: (item.class_name, item.name, item.trainer_id))
    return references


def write_location_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output_path)
