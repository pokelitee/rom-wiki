from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.map_headers import (
    code_load_address,
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.trainers import extract_trainer_dataset
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    BonusEncounterSpecies,
    EncounterMapLocation,
    EventMapLocation,
    LocationConnection,
    LocationDailyEncounterPool,
    LocationGameCornerPrize,
    LocationHoneyTree,
    LocationItem,
    LocationNpcTrade,
    LocationPokemonGift,
    LocationRoamingActivation,
    LocationShop,
    LocationShopItem,
    LocationStaticEncounter,
    LocationTrainerReference,
    LocationWarp,
    RecordProvenance,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for location extraction")
    profile = result.match.profile
    extraction_format = get_engine(profile.engine).formats.location_extraction
    if extraction_format == "archive-encounter-map":
        return _extract_encounter_map_location_dataset(
            result,
            trainer_dataset,
            static_encounter_dataset,
            item_dataset,
            mart_dataset,
            trade_dataset,
        )
    if extraction_format == "arm9-encounter-map":
        return _extract_arm9_encounter_map_location_dataset(result)
    if extraction_format == "arm9-event-map":
        return _extract_arm9_event_map_location_dataset(
            result,
            trainer_dataset,
            static_encounter_dataset,
            item_dataset,
            mart_dataset,
            trade_dataset,
        )
    raise DataSourceError(
        f"Unsupported location extraction format: {extraction_format!r}"
    )


def _extract_arm9_encounter_map_location_dataset(
    result: InspectionResult,
) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        encounters_path = profile.layout["encounters"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    encounters = platform.archive_cls.from_bytes(
        filesystem.read(encounters_path),
        allow_truncated=profile.parameters.get("encounters_allow_truncated", False),
    )
    arm9_data = read_code_binary(platform, result.image, engine)
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=map_names_path,
        table_offset=table_offset,
        count=count,
        location_names_member=location_names_member,
    )
    null_encounter_id = profile.parameters.get(
        "null_encounter_id", engine.ENCOUNTER_MEMBER_NONE
    )
    records = []
    for header in headers:
        encounter_id = header.encounter_id
        encounter_map_index = None if encounter_id == null_encounter_id else encounter_id
        if encounter_map_index is not None and encounter_map_index >= len(
            encounters.members
        ):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing encounter "
                f"member {encounter_map_index}"
            )
        records.append(
            EncounterMapLocation(
                header_id=header.header_id,
                name=location_names[header.location_name_id],
                encounter_map_index=encounter_map_index,
                matrix_id=header.matrix_id,
                provenance=RecordProvenance(
                    source="rom", archive="arm9", member=header.header_id
                ),
            ).to_dict()
        )
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "location_names": {
                "archive": messages_path,
                "member": location_names_member,
            },
        },
        "records": records,
    }


def _extract_arm9_event_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        events_path = profile.layout["events"]
        matrices_path = profile.layout["map_matrices"]
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        scripts_path = profile.layout["scripts"]
        item_data_path = profile.layout["item_data"]
        npc_trades_path = profile.layout["npc_trades"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        item_names_member = profile.parameters["item_names_member"]
        pokemon_names_member = profile.parameters["pokemon_names_member"]
        npc_trade_names_member = profile.parameters["npc_trade_names_member"]
        common_mart_inventory_offset = profile.parameters[
            "common_mart_inventory_offset"
        ]
        specialty_mart_pointer_table_offset = profile.parameters[
            "specialty_mart_pointer_table_offset"
        ]
        specialty_mart_inventory_count = profile.parameters[
            "specialty_mart_inventory_count"
        ]
        static_encounter_location_metadata = profile.parameters.get(
            "static_encounter_locations", []
        )
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    # The following features are Platinum-specific (decorations, seals, and the
    # Battle Frontier were never in Diamond/Pearl; honey trees, Trophy Garden,
    # and the Great Marsh are Sinnoh-only and have no Unova equivalent). They
    # are optional per profile/engine so a future non-Sinnoh engine or a
    # Diamond/Pearl profile can omit them entirely instead of crashing.
    bonus_encounters_path = profile.layout.get("bonus_encounters")
    decoration_names_member = profile.parameters.get("decoration_names_member")
    decoration_name_count = profile.parameters.get("decoration_name_count", 0)
    seal_names_member = profile.parameters.get("seal_names_member")
    decoration_mart_inventory_start = profile.parameters.get(
        "decoration_mart_inventory_start", 0
    )
    decoration_mart_inventory_count = profile.parameters.get(
        "decoration_mart_inventory_count", 0
    )
    decoration_price_table_offset = profile.parameters.get(
        "decoration_price_table_offset"
    )
    seal_mart_inventory_start = profile.parameters.get("seal_mart_inventory_start", 0)
    seal_mart_inventory_count = profile.parameters.get("seal_mart_inventory_count", 0)
    seal_price_table_offset = profile.parameters.get("seal_price_table_offset")
    frontier_mart_inventory_count = profile.parameters.get(
        "frontier_mart_inventory_count", 0
    )
    frontier_price_overlay_id = profile.parameters.get("frontier_price_overlay_id")
    frontier_price_table_offset = profile.parameters.get("frontier_price_table_offset")
    frontier_price_record_count = profile.parameters.get(
        "frontier_price_record_count", 0
    )
    game_corner_prize_table_offset = profile.parameters.get(
        "game_corner_prize_table_offset"
    )
    game_corner_prize_count = profile.parameters.get("game_corner_prize_count", 0)

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).locations

    null_event_id = profile.parameters.get("null_event_id", engine.ARCHIVE_MEMBER_NONE)
    null_encounter_id = profile.parameters.get(
        "null_encounter_id", engine.ARCHIVE_MEMBER_NONE
    )
    dynamic_warp_header_id = profile.parameters.get(
        "dynamic_warp_header_id", engine.DYNAMIC_WARP_HEADER_ID
    )
    dynamic_warp_id = profile.parameters.get("dynamic_warp_id", engine.DYNAMIC_WARP_ID)
    matrix_void_header_ids = frozenset(
        profile.parameters.get("matrix_void_header_ids", engine.MATRIX_VOID_HEADER_IDS)
    )
    honey_tree_header_ids = frozenset(
        profile.parameters.get(
            "honey_tree_header_ids", getattr(engine, "HONEY_TREE_HEADER_IDS", ())
        )
    )
    great_marsh_header_ids = frozenset(
        profile.parameters.get(
            "great_marsh_header_ids", getattr(engine, "GREAT_MARSH_HEADER_IDS", ())
        )
    )
    trophy_garden_header_id = profile.parameters.get(
        "trophy_garden_header_id", getattr(engine, "TROPHY_GARDEN_HEADER_ID", None)
    )
    game_corner_header_id = profile.parameters.get(
        "game_corner_prize_exchange_header_id",
        getattr(engine, "GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID", None),
    )
    arm9_load_address = code_load_address(platform, result.image)

    filesystem = platform.filesystem_from_image(result.image)
    arm9_data = read_code_binary(platform, result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=map_names_path,
        table_offset=table_offset,
        count=count,
        location_names_member=location_names_member,
    )
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    if game_corner_prize_table_offset is not None:
        game_corner_prizes = tuple(
            LocationGameCornerPrize(
                item_id=prize.item_id,
                name=item_names[prize.item_id],
                price=prize.price,
            )
            for prize in engine.parse_game_corner_prizes(
                arm9_data,
                offset=game_corner_prize_table_offset,
                count=game_corner_prize_count,
                item_count=len(item_names),
            )
        )
    else:
        game_corner_prizes = ()
    pokemon_names = engine.parse_english_message_archive(
        messages.read(pokemon_names_member)
    )
    npc_trade_names = engine.parse_english_message_archive(
        messages.read(npc_trade_names_member)
    )
    if decoration_names_member is not None:
        decoration_names = engine.parse_english_message_archive(
            messages.read(decoration_names_member), limit=decoration_name_count
        )
        decoration_prices = engine.parse_decoration_price_table(
            arm9_data,
            offset=decoration_price_table_offset,
            decoration_count=len(decoration_names),
        )
    else:
        decoration_names = ()
        decoration_prices = ()
    if seal_names_member is not None:
        seal_names = engine.parse_english_message_archive(
            messages.read(seal_names_member)
        )
        seal_prices = engine.parse_seal_price_table(
            arm9_data, offset=seal_price_table_offset, seal_count=len(seal_names)
        )
    else:
        seal_names = ()
        seal_prices = ()
    if frontier_price_overlay_id is not None:
        _, frontier_overlay = platform.read_overlay(
            result.image, frontier_price_overlay_id
        )
        frontier_prices = engine.parse_frontier_price_table(
            frontier_overlay,
            offset=frontier_price_table_offset,
            record_count=frontier_price_record_count,
        )
    else:
        frontier_prices = {}
    item_data = platform.archive_cls.from_bytes(filesystem.read(item_data_path))
    item_archive_map_offset, item_data_members = engine.find_item_archive_members(
        arm9_data,
        item_count=len(item_names),
        data_member_count=len(item_data.members),
    )
    item_prices = tuple(
        engine.parse_item_price(item_data.read(data_member))
        for data_member in item_data_members
    )
    npc_trades = platform.archive_cls.from_bytes(filesystem.read(npc_trades_path))
    if len(npc_trade_names) != len(npc_trades.members) * 2:
        raise InvalidRomError(
            "NPC trade name bank must contain one nickname and OT name per trade"
        )
    npc_trade_records = tuple(
        engine.parse_npc_trade_record(
            npc_trades.read(index),
            species_count=len(pokemon_names),
            item_count=len(item_names),
        )
        for index in range(len(npc_trades.members))
    )
    honey_tree: LocationHoneyTree | None = None
    trophy_garden_pool: LocationDailyEncounterPool | None = None
    great_marsh_pool: LocationDailyEncounterPool | None = None
    if bonus_encounters_path is not None:
        bonus_encounters = platform.archive_cls.from_bytes(
            filesystem.read(bonus_encounters_path)
        )

        def _bonus_species(member: int) -> tuple[BonusEncounterSpecies, ...]:
            return tuple(
                BonusEncounterSpecies(
                    species_id=species_id, name=pokemon_names[species_id]
                )
                for species_id in engine.parse_species_list(
                    bonus_encounters.read(member)
                )
            )

        if hasattr(engine, "GEN4_HONEY_TREE_COMMON_MEMBER"):
            honey_tree = LocationHoneyTree(
                common=_bonus_species(engine.GEN4_HONEY_TREE_COMMON_MEMBER),
                uncommon=_bonus_species(engine.GEN4_HONEY_TREE_UNCOMMON_MEMBER),
                rare=_bonus_species(engine.GEN4_HONEY_TREE_RARE_MEMBER),
            )
        if hasattr(engine, "GEN4_TROPHY_GARDEN_MEMBER"):
            trophy_garden_pool = LocationDailyEncounterPool(
                kind="trophy_garden",
                species=_bonus_species(engine.GEN4_TROPHY_GARDEN_MEMBER),
                pre_national_dex_species=None,
            )
        if hasattr(engine, "GEN4_GREAT_MARSH_POST_NATIONAL_DEX_MEMBER"):
            great_marsh_pool = LocationDailyEncounterPool(
                kind="great_marsh",
                species=_bonus_species(
                    engine.GEN4_GREAT_MARSH_POST_NATIONAL_DEX_MEMBER
                ),
                pre_national_dex_species=_bonus_species(
                    engine.GEN4_GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER
                ),
            )
    common_mart_items = engine.parse_common_mart_inventory(
        arm9_data, offset=common_mart_inventory_offset, item_count=len(item_names)
    )
    specialty_mart_inventories = engine.parse_specialty_mart_inventories(
        arm9_data,
        pointer_table_offset=specialty_mart_pointer_table_offset,
        inventory_count=specialty_mart_inventory_count,
        load_address=arm9_load_address,
        item_count=len(item_names),
    )
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), allow_truncated=True
    )
    referenced_script_ids = {header.script_file_id for header in headers}
    roaming_by_script = {
        script_file_id: tuple(
            LocationRoamingActivation(
                slot=command.slot,
                species_id=engine.ROAMING_SLOT_SPECIES_IDS[command.slot],
                species_name=pokemon_names[
                    engine.ROAMING_SLOT_SPECIES_IDS[command.slot]
                ],
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
            for command in engine.parse_roaming_activation_commands(
                scripts.read(script_file_id)
            )
        )
        for script_file_id in referenced_script_ids
    }
    roaming_activation_count = sum(
        len(activations) for activations in roaming_by_script.values()
    )
    events = platform.archive_cls.from_bytes(filesystem.read(events_path))
    matrices = platform.archive_cls.from_bytes(filesystem.read(matrices_path))
    shops_by_script: dict[int, tuple[LocationShop, ...]] = {}
    gifts_by_script: dict[int, tuple[LocationPokemonGift, ...]] = {}
    npc_trades_by_script: dict[int, tuple[LocationNpcTrade, ...]] = {}
    static_encounters_by_location: dict[
        tuple[int, int], tuple[LocationStaticEncounter, ...]
    ] = {}
    header_ids_by_script: dict[int, list[int]] = defaultdict(list)
    for header in headers:
        header_ids_by_script[header.script_file_id].append(header.header_id)
    static_encounter_header_by_command = {
        (metadata["script_member"], metadata["command_offset"]): metadata[
            "map_header_id"
        ]
        for metadata in static_encounter_location_metadata
    }
    if len(static_encounter_header_by_command) != len(
        static_encounter_location_metadata
    ):
        raise ProfileError("Static encounter location metadata contains duplicates")
    events_by_id: dict[int, Any] = {}
    items_by_event: dict[int, tuple[LocationItem, ...]] = {}
    raw_warps_by_header: dict[int, tuple[Any, ...]] = {}
    raw_items_by_header: dict[int, tuple[LocationItem, ...]] = {}
    for header in headers:
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
            events_by_id[header.event_file_id] = engine.parse_map_events(
                events.read(header.event_file_id), event_file_id=header.event_file_id
            )
            items_by_event[header.event_file_id] = _extract_event_map_location_items(
                engine, events_by_id[header.event_file_id], item_names
            )
        raw_warps_by_header[header.header_id] = events_by_id[header.event_file_id].warps
        raw_items_by_header[header.header_id] = items_by_event[header.event_file_id]

    connections = _extract_event_map_connections(
        engine, headers, matrices, location_names, matrix_void_header_ids
    )
    trainers = _extract_trainer_references(result, trainer_dataset)
    records = []
    for header in headers:
        if header.script_file_id >= len(scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{header.script_file_id}"
            )
        if header.script_file_id not in shops_by_script:
            shops_by_script[header.script_file_id] = _extract_event_map_location_shops(
                engine,
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
            gifts_by_script[header.script_file_id] = (
                _extract_event_map_location_pokemon_gifts(
                    engine,
                    scripts.read(header.script_file_id),
                    script_file_id=header.script_file_id,
                    pokemon_names=pokemon_names,
                    item_names=item_names,
                )
            )
        if header.script_file_id not in npc_trades_by_script:
            npc_trades_by_script[header.script_file_id] = (
                _extract_event_map_location_npc_trades(
                    engine,
                    scripts.read(header.script_file_id),
                    script_file_id=header.script_file_id,
                    trade_records=npc_trade_records,
                    trade_names=npc_trade_names,
                    pokemon_names=pokemon_names,
                    item_names=item_names,
                )
            )
        static_encounter_location_key = (
            header.script_file_id,
            header.header_id,
        )
        if static_encounter_location_key not in static_encounters_by_location:
            static_encounters_by_location[static_encounter_location_key] = (
                _extract_event_map_location_static_encounters(
                    engine,
                    scripts.read(header.script_file_id),
                    script_file_id=header.script_file_id,
                    map_header_id=header.header_id,
                    script_is_shared=(
                        len(header_ids_by_script[header.script_file_id]) > 1
                    ),
                    explicit_header_by_command=(static_encounter_header_by_command),
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
            EventMapLocation(
                header_id=header.header_id,
                internal_name=header.internal_name,
                location_name_id=header.location_name_id,
                name=location_names[header.location_name_id],
                matrix_id=header.matrix_id,
                area_data_id=header.area_data_id,
                level_script_id=header.level_script_id,
                text_archive_id=header.text_archive_id,
                day_music_id=header.day_music_id,
                night_music_id=header.night_music_id,
                weather_id=header.weather_id,
                camera_id=header.camera_id,
                map_flags=header.flags,
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
                static_encounters=static_encounters_by_location[
                    static_encounter_location_key
                ],
                roaming_activations=roaming_by_script[header.script_file_id],
                npc_trades=npc_trades_by_script[header.script_file_id],
                honey_tree=(
                    honey_tree if header.header_id in honey_tree_header_ids else None
                ),
                daily_encounter_pool=(
                    great_marsh_pool
                    if header.header_id in great_marsh_header_ids
                    else trophy_garden_pool
                    if header.header_id == trophy_garden_header_id
                    else None
                ),
                game_corner_prizes=(
                    game_corner_prizes
                    if header.header_id == game_corner_header_id
                    else ()
                ),
                provenance=RecordProvenance(
                    source="rom", archive="arm9", member=header.header_id
                ),
            ).to_dict()
        )
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
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
            item.kind == "hidden" for items in items_by_event.values() for item in items
        ),
        "location_item_reference_count": sum(
            len(record["items"]) for record in records
        ),
        "shop_count": sum(len(record["shops"]) for record in records),
        "shop_item_reference_count": sum(
            len(shop["items"]) for record in records for shop in record["shops"]
        ),
        "pokemon_gift_count": sum(len(record["pokemon_gifts"]) for record in records),
        "npc_trade_count": sum(len(record["npc_trades"]) for record in records),
        "static_encounter_count": sum(
            len(record["static_encounters"]) for record in records
        ),
        "roaming_activation_count": roaming_activation_count,
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
                "egg_command_discovery": "party-capacity-signature",
            },
            "npc_trades": {
                "archive": npc_trades_path,
                "scripts_archive": scripts_path,
                "command": "InitNPCTrade",
                "names": {
                    "archive": messages_path,
                    "member": npc_trade_names_member,
                },
            },
            "static_encounters": {
                "scripts_archive": scripts_path,
                "commands": [
                    "WildBattle",
                    "LegendaryBattle",
                    "FatefulEncounter",
                    "GiratinaOriginBattle",
                ],
                "location_overrides": static_encounter_location_metadata,
            },
            "roaming_pokemon": {
                "scripts_archive": scripts_path,
                "command": "ActivateRoamingPokemon",
                "slot_count": engine.ROAMING_SLOT_COUNT,
            },
            "decoration_names": (
                {
                    "archive": messages_path,
                    "member": decoration_names_member,
                    "count": decoration_name_count,
                }
                if decoration_names_member is not None
                else None
            ),
            "seal_names": (
                {
                    "archive": messages_path,
                    "member": seal_names_member,
                }
                if seal_names_member is not None
                else None
            ),
            "shops": {
                "scripts_archive": scripts_path,
                "item_data_archive": item_data_path,
                "item_archive_map_arm9_offset": item_archive_map_offset,
                "common_inventory_arm9_offset": common_mart_inventory_offset,
                "specialty_pointer_table_arm9_offset": (
                    specialty_mart_pointer_table_offset
                ),
                "decoration_price_table_arm9_offset": (decoration_price_table_offset),
                "seal_price_table_arm9_offset": seal_price_table_offset,
                "frontier_price_table": (
                    {
                        "overlay_id": frontier_price_overlay_id,
                        "offset": frontier_price_table_offset,
                        "record_count": frontier_price_record_count,
                    }
                    if frontier_price_overlay_id is not None
                    else None
                ),
            },
        },
        "records": records,
    }


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


def _extract_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Each map header's display name, its wild-encounter-table cross-
    # reference, its real trainers, its real warps, its real static
    # (gift/single) Pokémon encounters, its real outdoor connections, and its
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
    messages_path = profile.layout["messages"]
    map_headers = platform.archive_cls.from_bytes(filesystem.read(map_headers_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    headers = engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )
    script_file_ids = engine.parse_map_header_script_files(map_headers.read(0))
    trainers_by_header = _extract_trainer_references(result, trainer_dataset)
    overworld_objects = platform.archive_cls.from_bytes(
        filesystem.read(overworld_objects_path), **field_archive_options
    )
    map_matrices = platform.archive_cls.from_bytes(filesystem.read(map_matrices_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **field_archive_options
    )
    script_headers = _resolve_gen5_script_locations(
        engine,
        headers,
        script_file_ids,
        scripts,
        overworld_objects,
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
        items = []
        shops = []
        seen_vendor_ids: set[str] = set()
        script_file_id = script_file_ids[header.header_id]
        if header.header_id < len(overworld_objects.members):
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
                                availability=(
                                    "Stock changes with badge progression."
                                ),
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
        if header.header_id < len(overworld_objects.members):
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
            "map_matrices_archive": map_matrices_path,
            "scripts_archive": scripts_path,
            "map_names": {"archive": messages_path, "member": map_names_member},
        },
        "records": records,
    }


def _extract_event_map_location_shops(
    engine: Any,
    script: bytes,
    *,
    script_file_id: int,
    common_items: tuple[Any, ...],
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
    for command in engine.parse_mart_commands(script):
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
                (item_id, None) for item_id in specialty_inventories[inventory_index]
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
                schedule=engine.shop_schedule_label(
                    command.kind, command.inventory_id
                ),
            )
        )
    return tuple(shops)


def _extract_event_map_location_pokemon_gifts(
    engine: Any,
    script: bytes,
    *,
    script_file_id: int,
    pokemon_names: tuple[str, ...],
    item_names: tuple[str, ...],
) -> tuple[LocationPokemonGift, ...]:
    gifts = []
    for command in engine.parse_pokemon_gift_commands(
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
    for command in engine.parse_egg_gift_commands(
        script, species_count=len(pokemon_names)
    ):
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


def _extract_event_map_location_static_encounters(
    engine: Any,
    script: bytes,
    *,
    script_file_id: int,
    map_header_id: int,
    script_is_shared: bool,
    explicit_header_by_command: dict[tuple[int, int], int],
    pokemon_names: tuple[str, ...],
) -> tuple[LocationStaticEncounter, ...]:
    encounters = []
    for command in engine.parse_static_encounter_commands(
        script, species_count=len(pokemon_names)
    ):
        command_key = (script_file_id, command.offset)
        explicit_header_id = explicit_header_by_command.get(command_key)
        if explicit_header_id is not None:
            if explicit_header_id != map_header_id:
                continue
        elif script_is_shared:
            raise ProfileError(
                "Static encounter in shared script member "
                f"{script_file_id} at 0x{command.offset:X} requires a map-header "
                "location override"
            )
        encounters.append(
            LocationStaticEncounter(
                species_id=command.species_id,
                name=pokemon_names[command.species_id],
                level=command.level,
                command=command.command,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(encounters)


def _extract_event_map_location_npc_trades(
    engine: Any,
    script: bytes,
    *,
    script_file_id: int,
    trade_records: tuple[Any, ...],
    trade_names: tuple[str, ...],
    pokemon_names: tuple[str, ...],
    item_names: tuple[str, ...],
) -> tuple[LocationNpcTrade, ...]:
    trades = []
    trade_count = len(trade_records)
    for command in engine.parse_npc_trade_commands(script, trade_count=trade_count):
        trade = trade_records[command.trade_id]
        held_item_id = trade.held_item_id
        trades.append(
            LocationNpcTrade(
                trade_id=command.trade_id,
                requested_species_id=trade.requested_species_id,
                requested_species_name=pokemon_names[trade.requested_species_id],
                offered_species_id=trade.offered_species_id,
                offered_species_name=pokemon_names[trade.offered_species_id],
                nickname=trade_names[command.trade_id],
                ivs=trade.ivs,
                nature=trade.nature,
                held_item_id=held_item_id,
                held_item_name=(
                    item_names[held_item_id] if held_item_id is not None else None
                ),
                ot_name=trade_names[trade_count + command.trade_id],
                ot_id=trade.ot_id,
                ot_gender="Female" if trade.ot_gender else "Male",
                language=engine.trade_language_name(trade.language_id),
                personality=trade.personality,
                unknown_values=trade.unknown_values,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(trades)


def _extract_event_map_location_items(
    engine: Any, events: Any, item_names: tuple[str, ...]
) -> tuple[LocationItem, ...]:
    items = []
    for event in events.objects:
        item_id = engine.resolve_visible_item_id(event, item_count=len(item_names))
        if item_id is None:
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
        item_id = engine.resolve_hidden_item_id(event, item_count=len(item_names))
        if item_id is None:
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


def _extract_event_map_connections(
    engine: Any,
    headers: tuple[Any, ...],
    matrices: Any,
    location_names: tuple[str, ...],
    void_header_ids: frozenset[int],
) -> dict[int, list[LocationConnection]]:
    directions: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for matrix_id in sorted({header.matrix_id for header in headers}):
        if matrix_id >= len(matrices.members):
            raise InvalidRomError(f"Map header references missing matrix {matrix_id}")
        matrix = engine.parse_map_matrix(matrices.read(matrix_id), matrix_id=matrix_id)
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
    trainer_dataset: dict[str, Any] | None = None,
) -> dict[int, list[LocationTrainerReference]]:
    references: dict[int, list[LocationTrainerReference]] = defaultdict(list)
    seen: set[tuple[int, int, str]] = set()
    trainers = trainer_dataset or extract_trainer_dataset(result)
    for trainer in trainers["records"]:
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
    `_extract_event_map_connections` algorithm, adapted to the differently-
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
) -> dict[int, tuple[int, ...]]:
    """Map dedicated and common script members to every proven map caller."""
    member_count = len(scripts.members)
    owners: dict[int, set[int]] = defaultdict(set)
    for header in headers:
        owners[script_file_ids[header.header_id]].add(header.header_id)
        if header.header_id >= len(overworld_objects.members):
            continue
        overworld = overworld_objects.read(header.header_id)
        references = [
            npc.script_used for npc in engine.parse_overworld_npcs(overworld)
        ]
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
                "requested_species_name": pokemon_names[
                    record["requested_species_id"]
                ],
                "offered_species_name": pokemon_names[
                    record["offered_species_id"]
                ],
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


def write_location_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
