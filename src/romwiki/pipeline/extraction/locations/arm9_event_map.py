from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.helpers import (
    EventMapItemScan,
    extract_event_map_connections,
    extract_event_map_items,
    extract_trainer_references,
)
from romwiki.pipeline.extraction.map_headers import (
    code_load_address,
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    BonusEncounterSpecies,
    EventMapLocation,
    LocationDailyEncounterPool,
    LocationGameCornerPrize,
    LocationHoneyTree,
    LocationItem,
    LocationNpcTrade,
    LocationPokemonGift,
    LocationRoamingActivation,
    LocationScriptAwardedItem,
    LocationShop,
    LocationShopItem,
    LocationStaticEncounter,
    LocationWarp,
    RecordProvenance,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class _EventMapNames:
    location: tuple[str, ...]
    item: tuple[str, ...]
    pokemon: tuple[str, ...]
    npc_trade: tuple[str, ...]
    decoration: tuple[str, ...]
    seal: tuple[str, ...]


@dataclass(frozen=True)
class _EventMapShopCatalogs:
    common_items: tuple[Any, ...]
    specialty_inventories: tuple[tuple[int, ...], ...]
    decoration_inventory_start: int
    decoration_inventory_count: int
    seal_inventory_start: int
    seal_inventory_count: int
    frontier_inventory_count: int
    item_prices: tuple[int, ...]
    decoration_prices: tuple[int, ...]
    seal_prices: tuple[int, ...]
    frontier_prices: dict[int, int]


@dataclass(frozen=True)
class _EventMapFeatures:
    null_event_id: int
    null_encounter_id: int
    dynamic_warp_header_id: int
    dynamic_warp_id: int
    honey_tree_header_ids: frozenset[int]
    great_marsh_header_ids: frozenset[int]
    trophy_garden_header_id: int | None
    game_corner_header_id: int | None
    honey_tree: LocationHoneyTree | None
    trophy_garden_pool: LocationDailyEncounterPool | None
    great_marsh_pool: LocationDailyEncounterPool | None
    game_corner_prizes: tuple[LocationGameCornerPrize, ...]


@dataclass(frozen=True)
class _EventMapRecordContext:
    profile: Any
    engine: Any
    headers: tuple[Any, ...]
    scripts: Any
    names: _EventMapNames
    shops: _EventMapShopCatalogs
    features: _EventMapFeatures
    npc_trade_records: tuple[Any, ...]
    roaming_by_script: dict[int, tuple[LocationRoamingActivation, ...]]
    raw_warps_by_header: dict[int, tuple[Any, ...]]
    raw_items_by_header: dict[int, tuple[LocationItem, ...]]
    connections: dict[int, list[Any]]
    trainers: dict[int, list[Any]]
    static_encounter_location_metadata: list[dict[str, int]]


@dataclass(frozen=True)
class _EventMapLoadedSource:
    profile: Any
    engine: Any
    platform: Any
    filesystem: Any
    headers: tuple[Any, ...]
    scripts: Any
    names: _EventMapNames
    shops: _EventMapShopCatalogs
    features: _EventMapFeatures
    npc_trade_records: tuple[Any, ...]
    roaming_by_script: dict[int, tuple[LocationRoamingActivation, ...]]
    roaming_activation_count: int
    events_path: str
    matrices_path: str
    matrix_void_header_ids: frozenset[int]
    static_encounter_location_metadata: list[dict[str, int]]
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class _EventMapRelationships:
    items_by_event: dict[int, EventMapItemScan]
    raw_warps_by_header: dict[int, tuple[Any, ...]]
    raw_items_by_header: dict[int, tuple[LocationItem, ...]]
    connections: dict[int, list[Any]]
    trainers: dict[int, list[Any]]


def extract_arm9_event_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = _load_event_map_source(result)
    relationships = _collect_event_map_relationships(result, source, trainer_dataset)
    records = _build_event_map_location_records(
        _EventMapRecordContext(
            profile=source.profile,
            engine=source.engine,
            headers=source.headers,
            scripts=source.scripts,
            names=source.names,
            shops=source.shops,
            features=source.features,
            npc_trade_records=source.npc_trade_records,
            roaming_by_script=source.roaming_by_script,
            raw_warps_by_header=relationships.raw_warps_by_header,
            raw_items_by_header=relationships.raw_items_by_header,
            connections=relationships.connections,
            trainers=relationships.trainers,
            static_encounter_location_metadata=(
                source.static_encounter_location_metadata
            ),
        )
    )
    return _build_event_map_location_envelope(source, relationships, records)


def _load_event_map_source(
    result: InspectionResult,
) -> _EventMapLoadedSource:
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
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
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
        profile.parameters.get("honey_tree_header_ids", engine.HONEY_TREE_HEADER_IDS)
    )
    great_marsh_header_ids = frozenset(
        profile.parameters.get("great_marsh_header_ids", engine.GREAT_MARSH_HEADER_IDS)
    )
    trophy_garden_header_id = profile.parameters.get(
        "trophy_garden_header_id", engine.TROPHY_GARDEN_HEADER_ID
    )
    game_corner_header_id = profile.parameters.get(
        "game_corner_prize_exchange_header_id",
        engine.GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID,
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
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
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
        if platform.read_overlay is None:
            raise ProfileError(
                f"Platform {profile.platform!r} does not support overlays"
            )
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

        honey_tree = LocationHoneyTree(
            common=_bonus_species(engine.HONEY_TREE_COMMON_MEMBER),
            uncommon=_bonus_species(engine.HONEY_TREE_UNCOMMON_MEMBER),
            rare=_bonus_species(engine.HONEY_TREE_RARE_MEMBER),
        )
        trophy_garden_pool = LocationDailyEncounterPool(
            kind="trophy_garden",
            species=_bonus_species(engine.TROPHY_GARDEN_MEMBER),
            pre_national_dex_species=None,
        )
        great_marsh_pool = LocationDailyEncounterPool(
            kind="great_marsh",
            species=_bonus_species(engine.GREAT_MARSH_POST_NATIONAL_DEX_MEMBER),
            pre_national_dex_species=_bonus_species(
                engine.GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER
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
    names = _EventMapNames(
        location=location_names,
        item=item_names,
        pokemon=pokemon_names,
        npc_trade=npc_trade_names,
        decoration=decoration_names,
        seal=seal_names,
    )
    shops = _EventMapShopCatalogs(
        common_items=common_mart_items,
        specialty_inventories=specialty_mart_inventories,
        decoration_inventory_start=decoration_mart_inventory_start,
        decoration_inventory_count=decoration_mart_inventory_count,
        seal_inventory_start=seal_mart_inventory_start,
        seal_inventory_count=seal_mart_inventory_count,
        frontier_inventory_count=frontier_mart_inventory_count,
        item_prices=item_prices,
        decoration_prices=decoration_prices,
        seal_prices=seal_prices,
        frontier_prices=frontier_prices,
    )
    features = _EventMapFeatures(
        null_event_id=null_event_id,
        null_encounter_id=null_encounter_id,
        dynamic_warp_header_id=dynamic_warp_header_id,
        dynamic_warp_id=dynamic_warp_id,
        honey_tree_header_ids=honey_tree_header_ids,
        great_marsh_header_ids=great_marsh_header_ids,
        trophy_garden_header_id=trophy_garden_header_id,
        game_corner_header_id=game_corner_header_id,
        honey_tree=honey_tree,
        trophy_garden_pool=trophy_garden_pool,
        great_marsh_pool=great_marsh_pool,
        game_corner_prizes=game_corner_prizes,
    )
    source_metadata = {
        "rom_sha256": result.image.hashes.sha256,
        "events_archive": events_path,
        "map_matrices_archive": matrices_path,
        "map_headers": {"arm9_offset": table_offset, "count": count},
        "internal_names": map_names_path,
        "location_names": {
            "archive": messages_path,
            "member": location_names_member,
        },
        "item_names": {"archive": messages_path, "member": item_names_member},
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
            {"archive": messages_path, "member": seal_names_member}
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
            "decoration_price_table_arm9_offset": decoration_price_table_offset,
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
    }
    return _EventMapLoadedSource(
        profile=profile,
        engine=engine,
        platform=platform,
        filesystem=filesystem,
        headers=headers,
        scripts=scripts,
        names=names,
        shops=shops,
        features=features,
        npc_trade_records=npc_trade_records,
        roaming_by_script=roaming_by_script,
        roaming_activation_count=roaming_activation_count,
        events_path=events_path,
        matrices_path=matrices_path,
        matrix_void_header_ids=matrix_void_header_ids,
        static_encounter_location_metadata=static_encounter_location_metadata,
        source_metadata=source_metadata,
    )


def _collect_event_map_relationships(
    result: InspectionResult,
    source: _EventMapLoadedSource,
    trainer_dataset: dict[str, Any] | None,
) -> _EventMapRelationships:
    events = source.platform.archive_cls.from_bytes(
        source.filesystem.read(source.events_path)
    )
    matrices = source.platform.archive_cls.from_bytes(
        source.filesystem.read(source.matrices_path)
    )
    events_by_id: dict[int, Any] = {}
    items_by_event: dict[int, EventMapItemScan] = {}
    raw_warps_by_header: dict[int, tuple[Any, ...]] = {}
    raw_items_by_header: dict[int, tuple[LocationItem, ...]] = {}
    for header in source.headers:
        if header.event_file_id == source.features.null_event_id:
            raw_warps_by_header[header.header_id] = ()
            raw_items_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in events_by_id:
            events_by_id[header.event_file_id] = source.engine.parse_map_events(
                events.read(header.event_file_id),
                event_file_id=header.event_file_id,
            )
            items_by_event[header.event_file_id] = extract_event_map_items(
                source.engine,
                events_by_id[header.event_file_id],
                source.names.item,
            )
        raw_warps_by_header[header.header_id] = events_by_id[header.event_file_id].warps
        raw_items_by_header[header.header_id] = items_by_event[
            header.event_file_id
        ].items
    return _EventMapRelationships(
        items_by_event=items_by_event,
        raw_warps_by_header=raw_warps_by_header,
        raw_items_by_header=raw_items_by_header,
        connections=extract_event_map_connections(
            source.engine,
            source.headers,
            matrices,
            source.names.location,
            source.matrix_void_header_ids,
        ),
        trainers=extract_trainer_references(result, trainer_dataset),
    )


def _build_event_map_location_envelope(
    source: _EventMapLoadedSource,
    relationships: _EventMapRelationships,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": source.profile.id,
        "engine": source.profile.engine,
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
            for scan in relationships.items_by_event.values()
            for item in scan.items
        ),
        "hidden_item_count": sum(
            item.kind == "hidden"
            for scan in relationships.items_by_event.values()
            for item in scan.items
        ),
        "unresolved_visible_item_count": sum(
            scan.unresolved_visible_count
            for scan in relationships.items_by_event.values()
        ),
        "unresolved_hidden_item_count": sum(
            scan.unresolved_hidden_count
            for scan in relationships.items_by_event.values()
        ),
        "location_item_reference_count": sum(
            len(record["items"]) for record in records
        ),
        "script_awarded_item_reference_count": sum(
            len(record["script_awarded_items"]) for record in records
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
        "roaming_activation_count": source.roaming_activation_count,
        "source": source.source_metadata,
        "records": records,
    }


def _build_event_map_location_records(
    context: _EventMapRecordContext,
) -> list[dict[str, Any]]:
    shops_by_script: dict[int, tuple[LocationShop, ...]] = {}
    gifts_by_script: dict[int, tuple[LocationPokemonGift, ...]] = {}
    npc_trades_by_script: dict[int, tuple[LocationNpcTrade, ...]] = {}
    script_awarded_items_by_script: dict[
        int, tuple[LocationScriptAwardedItem, ...]
    ] = {}
    static_encounters_by_location: dict[
        tuple[int, int], tuple[LocationStaticEncounter, ...]
    ] = {}
    header_ids_by_script: dict[int, list[int]] = defaultdict(list)
    for header in context.headers:
        header_ids_by_script[header.script_file_id].append(header.header_id)
    static_encounter_header_by_command = {
        (metadata["script_member"], metadata["command_offset"]): metadata[
            "map_header_id"
        ]
        for metadata in context.static_encounter_location_metadata
    }
    if len(static_encounter_header_by_command) != len(
        context.static_encounter_location_metadata
    ):
        raise ProfileError("Static encounter location metadata contains duplicates")

    records = []
    for header in context.headers:
        section_name, section_name_source = resolve_location_section(
            context.profile,
            header_id=header.header_id,
            internal_name=header.internal_name,
        )
        if header.script_file_id >= len(context.scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{header.script_file_id}"
            )
        script = context.scripts.read(header.script_file_id)
        if header.script_file_id not in shops_by_script:
            shops_by_script[header.script_file_id] = _extract_event_map_location_shops(
                context.engine,
                script,
                script_file_id=header.script_file_id,
                common_items=context.shops.common_items,
                specialty_inventories=context.shops.specialty_inventories,
                decoration_inventory_start=(context.shops.decoration_inventory_start),
                decoration_inventory_count=context.shops.decoration_inventory_count,
                seal_inventory_start=context.shops.seal_inventory_start,
                seal_inventory_count=context.shops.seal_inventory_count,
                frontier_inventory_count=context.shops.frontier_inventory_count,
                item_names=context.names.item,
                item_prices=context.shops.item_prices,
                decoration_names=context.names.decoration,
                seal_names=context.names.seal,
                decoration_prices=context.shops.decoration_prices,
                seal_prices=context.shops.seal_prices,
                frontier_prices=context.shops.frontier_prices,
            )
        if header.script_file_id not in gifts_by_script:
            gifts_by_script[header.script_file_id] = (
                _extract_event_map_location_pokemon_gifts(
                    context.engine,
                    script,
                    script_file_id=header.script_file_id,
                    pokemon_names=context.names.pokemon,
                    item_names=context.names.item,
                )
            )
        if header.script_file_id not in npc_trades_by_script:
            npc_trades_by_script[header.script_file_id] = (
                _extract_event_map_location_npc_trades(
                    context.engine,
                    script,
                    script_file_id=header.script_file_id,
                    trade_records=context.npc_trade_records,
                    trade_names=context.names.npc_trade,
                    pokemon_names=context.names.pokemon,
                    item_names=context.names.item,
                )
            )
        if header.script_file_id not in script_awarded_items_by_script:
            script_awarded_items_by_script[header.script_file_id] = (
                _extract_event_map_location_script_awarded_items(
                    context.engine,
                    script,
                    script_file_id=header.script_file_id,
                    item_names=context.names.item,
                )
            )
        static_key = (header.script_file_id, header.header_id)
        if static_key not in static_encounters_by_location:
            static_encounters_by_location[static_key] = (
                _extract_event_map_location_static_encounters(
                    context.engine,
                    script,
                    script_file_id=header.script_file_id,
                    map_header_id=header.header_id,
                    script_is_shared=(
                        len(header_ids_by_script[header.script_file_id]) > 1
                    ),
                    explicit_header_by_command=static_encounter_header_by_command,
                    pokemon_names=context.names.pokemon,
                )
            )
        warps = _build_event_map_location_warps(context, header)
        records.append(
            _build_event_map_location_record(
                context,
                header,
                warps,
                shops=shops_by_script[header.script_file_id],
                gifts=gifts_by_script[header.script_file_id],
                static_encounters=static_encounters_by_location[static_key],
                npc_trades=npc_trades_by_script[header.script_file_id],
                script_awarded_items=script_awarded_items_by_script[
                    header.script_file_id
                ],
                section_name=section_name,
                section_name_source=section_name_source,
            )
        )
    return records


def _build_event_map_location_warps(
    context: _EventMapRecordContext, header: Any
) -> list[LocationWarp]:
    warps = []
    for warp in context.raw_warps_by_header[header.header_id]:
        dynamic = (
            warp.destination_header_id == context.features.dynamic_warp_header_id
            and warp.destination_warp_id == context.features.dynamic_warp_id
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
                    destination_section_name=None,
                    destination_internal_name=None,
                    destination_warp_exists=None,
                    dynamic=True,
                )
            )
            continue
        if not 0 <= warp.destination_header_id < len(context.headers):
            raise InvalidRomError(
                f"Map header {header.header_id} warp {warp.index} references "
                f"missing header {warp.destination_header_id}"
            )
        destination = context.headers[warp.destination_header_id]
        destination_warps = context.raw_warps_by_header[destination.header_id]
        destination_section_name, _ = resolve_location_section(
            context.profile,
            header_id=destination.header_id,
            internal_name=destination.internal_name,
        )
        warps.append(
            LocationWarp(
                index=warp.index,
                x=warp.x,
                z=warp.z,
                destination_header_id=destination.header_id,
                destination_warp_id=warp.destination_warp_id,
                destination_name=context.names.location[destination.location_name_id],
                destination_section_name=destination_section_name,
                destination_internal_name=destination.internal_name,
                destination_warp_exists=(
                    warp.destination_warp_id < len(destination_warps)
                ),
                dynamic=False,
            )
        )
    return warps


def _build_event_map_location_record(
    context: _EventMapRecordContext,
    header: Any,
    warps: list[LocationWarp],
    *,
    shops: tuple[LocationShop, ...],
    gifts: tuple[LocationPokemonGift, ...],
    static_encounters: tuple[LocationStaticEncounter, ...],
    npc_trades: tuple[LocationNpcTrade, ...],
    script_awarded_items: tuple[LocationScriptAwardedItem, ...],
    section_name: str | None,
    section_name_source: dict[str, str] | None,
) -> dict[str, Any]:
    features = context.features
    return EventMapLocation(
        header_id=header.header_id,
        internal_name=header.internal_name,
        location_name_id=header.location_name_id,
        name=context.names.location[header.location_name_id],
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
            if header.event_file_id == features.null_event_id
            else header.event_file_id
        ),
        encounter_id=(
            None
            if header.encounter_id == features.null_encounter_id
            else header.encounter_id
        ),
        warps=tuple(warps),
        connections=tuple(context.connections.get(header.header_id, ())),
        trainers=tuple(context.trainers.get(header.header_id, ())),
        items=context.raw_items_by_header[header.header_id],
        shops=shops,
        pokemon_gifts=gifts,
        static_encounters=static_encounters,
        roaming_activations=context.roaming_by_script[header.script_file_id],
        npc_trades=npc_trades,
        script_awarded_items=script_awarded_items,
        honey_tree=(
            features.honey_tree
            if header.header_id in features.honey_tree_header_ids
            else None
        ),
        daily_encounter_pool=(
            features.great_marsh_pool
            if header.header_id in features.great_marsh_header_ids
            else features.trophy_garden_pool
            if header.header_id == features.trophy_garden_header_id
            else None
        ),
        game_corner_prizes=(
            features.game_corner_prizes
            if header.header_id == features.game_corner_header_id
            else ()
        ),
        provenance=RecordProvenance(
            source="rom", archive="arm9", member=header.header_id
        ),
        section_name=section_name,
        section_name_source=section_name_source,
    ).to_dict()


def _extract_event_map_location_shops(
    engine: LocationConcern,
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
            source_items: Iterable[tuple[int, Any]] = (
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
                schedule=engine.shop_schedule_label(command.kind, command.inventory_id),
            )
        )
    return tuple(shops)


def _extract_event_map_location_pokemon_gifts(
    engine: LocationConcern,
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
    engine: LocationConcern,
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
                is_egg=False,
                command=command.command,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(encounters)


def _extract_event_map_location_npc_trades(
    engine: LocationConcern,
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
                contest_stats=trade.contest_stats,
                unused_values=trade.unused_values,
                script_file_id=script_file_id,
                command_offset=command.offset,
            )
        )
    return tuple(trades)


def _extract_event_map_location_script_awarded_items(
    engine: LocationConcern,
    script: bytes,
    *,
    script_file_id: int,
    item_names: tuple[str, ...],
) -> tuple[LocationScriptAwardedItem, ...]:
    """Resolve items an NPC's own dialogue script hands over directly.

    These never place an item-ball/hidden-item event on the map, so they are
    otherwise invisible to `extract_event_map_items` (e.g. a species-
    conditional gift from an "Item Fanatic"-style NPC).
    """
    return tuple(
        LocationScriptAwardedItem(
            item_id=award.item_id,
            name=item_names[award.item_id],
            quantity=award.quantity,
            script_file_id=script_file_id,
            command_offset=award.command_offset,
            command=award.command,
        )
        for award in engine.find_script_awarded_items(
            script, item_count=len(item_names)
        )
    )
