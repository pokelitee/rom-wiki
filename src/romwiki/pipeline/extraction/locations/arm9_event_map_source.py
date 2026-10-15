from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from romwiki.engines.concerns import LocationConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.event_map_shops import (
    EventMapShopCatalogs,
    EventMapShopSource,
    load_event_map_shop_source,
)
from romwiki.pipeline.extraction.map_headers import (
    code_load_address,
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.semantics.location_sections import (
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    BonusEncounterSpecies,
    LocationDailyEncounterPool,
    LocationGameCornerPrize,
    LocationHoneyTree,
    LocationRoamingActivation,
)
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class _EventMapLayout:
    events_path: str
    matrices_path: str
    map_names_path: str
    messages_path: str
    scripts_path: str
    item_data_path: str
    npc_trades_path: str
    count: int
    table_offset: int
    location_names_member: int
    item_names_member: int
    pokemon_names_member: int
    npc_trade_names_member: int
    static_encounter_location_metadata: list[dict[str, int]]


@dataclass(frozen=True)
class EventMapNames:
    location: tuple[str, ...]
    item: tuple[str, ...]
    pokemon: tuple[str, ...]
    npc_trade: tuple[str, ...]


@dataclass(frozen=True)
class _EventMapBonusPools:
    honey_tree: LocationHoneyTree | None
    trophy_garden_pool: LocationDailyEncounterPool | None
    great_marsh_pool: LocationDailyEncounterPool | None


@dataclass(frozen=True)
class EventMapFeatures:
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
class EventMapLoadedSource:
    profile: Any
    engine: Any
    platform: Any
    filesystem: Any
    headers: tuple[Any, ...]
    scripts: Any
    names: EventMapNames
    shops: EventMapShopCatalogs
    features: EventMapFeatures
    npc_trade_records: tuple[Any, ...]
    roaming_by_script: dict[int, tuple[LocationRoamingActivation, ...]]
    roaming_activation_count: int
    events_path: str
    matrices_path: str
    matrix_void_header_ids: frozenset[int]
    static_encounter_location_metadata: list[dict[str, int]]
    source_metadata: dict[str, Any]


def _read_event_map_layout(profile: Any) -> _EventMapLayout:
    try:
        return _EventMapLayout(
            events_path=profile.layout["events"],
            matrices_path=profile.layout["map_matrices"],
            map_names_path=profile.layout["map_names"],
            messages_path=profile.layout["messages"],
            scripts_path=profile.layout["scripts"],
            item_data_path=profile.layout["item_data"],
            npc_trades_path=profile.layout["npc_trades"],
            count=profile.parameters["map_header_count"],
            table_offset=profile.parameters["map_header_offset"],
            location_names_member=profile.parameters["location_names_member"],
            item_names_member=profile.parameters["item_names_member"],
            pokemon_names_member=profile.parameters["pokemon_names_member"],
            npc_trade_names_member=profile.parameters["npc_trade_names_member"],
            static_encounter_location_metadata=profile.parameters.get(
                "static_encounter_locations", []
            ),
        )
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error


def load_event_map_source(
    result: InspectionResult,
) -> EventMapLoadedSource:
    assert result.match is not None
    profile = result.match.profile
    layout = _read_event_map_layout(profile)
    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    arm9_data = read_code_binary(platform, result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(layout.messages_path))
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=layout.map_names_path,
        table_offset=layout.table_offset,
        count=layout.count,
        location_names_member=layout.location_names_member,
    )
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
    )
    names = _decode_event_map_names(engine, messages, layout, location_names)
    shop_source = load_event_map_shop_source(
        profile,
        engine,
        platform,
        result.image,
        filesystem=filesystem,
        arm9_data=arm9_data,
        arm9_load_address=code_load_address(platform, result.image),
        messages=messages,
        item_names=names.item,
        item_data_path=layout.item_data_path,
        scripts_path=layout.scripts_path,
        messages_path=layout.messages_path,
    )
    npc_trade_records = _decode_npc_trade_records(
        engine,
        platform.archive_cls.from_bytes(filesystem.read(layout.npc_trades_path)),
        names,
    )
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(layout.scripts_path), allow_truncated=True
    )
    roaming_by_script = _decode_roaming_activations(
        engine, headers, scripts, names.pokemon
    )
    return EventMapLoadedSource(
        profile=profile,
        engine=engine,
        platform=platform,
        filesystem=filesystem,
        headers=headers,
        scripts=scripts,
        names=names,
        shops=shop_source.catalogs,
        features=_resolve_event_map_features(
            profile, engine, platform, filesystem, arm9_data, names
        ),
        npc_trade_records=npc_trade_records,
        roaming_by_script=roaming_by_script,
        roaming_activation_count=sum(
            len(activations) for activations in roaming_by_script.values()
        ),
        events_path=layout.events_path,
        matrices_path=layout.matrices_path,
        matrix_void_header_ids=frozenset(
            profile.parameters.get(
                "matrix_void_header_ids", engine.MATRIX_VOID_HEADER_IDS
            )
        ),
        static_encounter_location_metadata=layout.static_encounter_location_metadata,
        source_metadata=_build_event_map_source_metadata(
            result, engine, layout, shop_source
        ),
    )


def _decode_event_map_names(
    engine: LocationConcern,
    messages: Any,
    layout: _EventMapLayout,
    location_names: tuple[str, ...],
) -> EventMapNames:
    return EventMapNames(
        location=location_names,
        item=engine.parse_english_message_archive(
            messages.read(layout.item_names_member)
        ),
        pokemon=engine.parse_english_message_archive(
            messages.read(layout.pokemon_names_member)
        ),
        npc_trade=engine.parse_english_message_archive(
            messages.read(layout.npc_trade_names_member)
        ),
    )


def _decode_npc_trade_records(
    engine: LocationConcern, npc_trades: Any, names: EventMapNames
) -> tuple[Any, ...]:
    if len(names.npc_trade) != len(npc_trades.members) * 2:
        raise InvalidRomError(
            "NPC trade name bank must contain one nickname and OT name per trade"
        )
    return tuple(
        engine.parse_npc_trade_record(
            npc_trades.read(index),
            species_count=len(names.pokemon),
            item_count=len(names.item),
        )
        for index in range(len(npc_trades.members))
    )


def _decode_roaming_activations(
    engine: LocationConcern,
    headers: tuple[Any, ...],
    scripts: Any,
    pokemon_names: tuple[str, ...],
) -> dict[int, tuple[LocationRoamingActivation, ...]]:
    referenced_script_ids = {header.script_file_id for header in headers}
    return {
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


def _resolve_event_map_features(
    profile: Any,
    engine: LocationConcern,
    platform: Any,
    filesystem: Any,
    arm9_data: bytes,
    names: EventMapNames,
) -> EventMapFeatures:
    parameters = profile.parameters
    bonus_pools = _decode_bonus_encounter_pools(
        engine, platform, filesystem, profile.layout.get("bonus_encounters"), names
    )
    return EventMapFeatures(
        null_event_id=profile.int_parameter(
            "null_event_id", engine.ARCHIVE_MEMBER_NONE
        ),
        null_encounter_id=profile.int_parameter(
            "null_encounter_id", engine.ARCHIVE_MEMBER_NONE
        ),
        dynamic_warp_header_id=profile.int_parameter(
            "dynamic_warp_header_id", engine.DYNAMIC_WARP_HEADER_ID
        ),
        dynamic_warp_id=profile.int_parameter(
            "dynamic_warp_id", engine.DYNAMIC_WARP_ID
        ),
        honey_tree_header_ids=frozenset(
            parameters.get("honey_tree_header_ids", engine.HONEY_TREE_HEADER_IDS)
        ),
        great_marsh_header_ids=frozenset(
            parameters.get("great_marsh_header_ids", engine.GREAT_MARSH_HEADER_IDS)
        ),
        trophy_garden_header_id=parameters.get(
            "trophy_garden_header_id", engine.TROPHY_GARDEN_HEADER_ID
        ),
        game_corner_header_id=parameters.get(
            "game_corner_prize_exchange_header_id",
            engine.GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID,
        ),
        honey_tree=bonus_pools.honey_tree,
        trophy_garden_pool=bonus_pools.trophy_garden_pool,
        great_marsh_pool=bonus_pools.great_marsh_pool,
        game_corner_prizes=_decode_game_corner_prizes(
            profile, engine, arm9_data, names.item
        ),
    )


def _decode_game_corner_prizes(
    profile: Any,
    engine: LocationConcern,
    arm9_data: bytes,
    item_names: tuple[str, ...],
) -> tuple[LocationGameCornerPrize, ...]:
    prize_table_offset = profile.optional_int_parameter(
        "game_corner_prize_table_offset"
    )
    if prize_table_offset is None:
        return ()
    return tuple(
        LocationGameCornerPrize(
            item_id=prize.item_id,
            name=item_names[prize.item_id],
            price=prize.price,
        )
        for prize in engine.parse_game_corner_prizes(
            arm9_data,
            offset=prize_table_offset,
            count=profile.int_parameter("game_corner_prize_count", 0),
            item_count=len(item_names),
        )
    )


def _decode_bonus_encounter_pools(
    engine: LocationConcern,
    platform: Any,
    filesystem: Any,
    bonus_encounters_path: str | None,
    names: EventMapNames,
) -> _EventMapBonusPools:
    # Honey trees, the Trophy Garden, and the Great Marsh are Sinnoh-only and
    # have no Unova equivalent, so a profile can omit their archive entirely.
    if bonus_encounters_path is None:
        return _EventMapBonusPools(
            honey_tree=None, trophy_garden_pool=None, great_marsh_pool=None
        )
    bonus_encounters = platform.archive_cls.from_bytes(
        filesystem.read(bonus_encounters_path)
    )
    species = partial(_decode_bonus_species, engine, bonus_encounters, names.pokemon)
    return _EventMapBonusPools(
        honey_tree=LocationHoneyTree(
            common=species(engine.HONEY_TREE_COMMON_MEMBER),
            uncommon=species(engine.HONEY_TREE_UNCOMMON_MEMBER),
            rare=species(engine.HONEY_TREE_RARE_MEMBER),
        ),
        trophy_garden_pool=LocationDailyEncounterPool(
            kind="trophy_garden",
            species=species(engine.TROPHY_GARDEN_MEMBER),
            pre_national_dex_species=None,
        ),
        great_marsh_pool=LocationDailyEncounterPool(
            kind="great_marsh",
            species=species(engine.GREAT_MARSH_POST_NATIONAL_DEX_MEMBER),
            pre_national_dex_species=species(
                engine.GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER
            ),
        ),
    )


def _decode_bonus_species(
    engine: LocationConcern,
    bonus_encounters: Any,
    pokemon_names: tuple[str, ...],
    member: int,
) -> tuple[BonusEncounterSpecies, ...]:
    return tuple(
        BonusEncounterSpecies(species_id=species_id, name=pokemon_names[species_id])
        for species_id in engine.parse_species_list(bonus_encounters.read(member))
    )


def _build_event_map_source_metadata(
    result: InspectionResult,
    engine: LocationConcern,
    layout: _EventMapLayout,
    shop_source: EventMapShopSource,
) -> dict[str, Any]:
    messages_path = layout.messages_path
    scripts_path = layout.scripts_path
    return {
        "rom_sha256": result.image.hashes.sha256,
        "events_archive": layout.events_path,
        "map_matrices_archive": layout.matrices_path,
        "map_headers": {"arm9_offset": layout.table_offset, "count": layout.count},
        "internal_names": layout.map_names_path,
        "location_names": {
            "archive": messages_path,
            "member": layout.location_names_member,
        },
        "item_names": {"archive": messages_path, "member": layout.item_names_member},
        "pokemon_names": {
            "archive": messages_path,
            "member": layout.pokemon_names_member,
        },
        "pokemon_gifts": {
            "scripts_archive": scripts_path,
            "egg_command_discovery": "party-capacity-signature",
        },
        "npc_trades": {
            "archive": layout.npc_trades_path,
            "scripts_archive": scripts_path,
            "command": "InitNPCTrade",
            "names": {
                "archive": messages_path,
                "member": layout.npc_trade_names_member,
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
            "location_overrides": layout.static_encounter_location_metadata,
        },
        "roaming_pokemon": {
            "scripts_archive": scripts_path,
            "command": "ActivateRoamingPokemon",
            "slot_count": engine.ROAMING_SLOT_COUNT,
        },
        "decoration_names": shop_source.decoration_names_metadata,
        "seal_names": shop_source.seal_names_metadata,
        "shops": shop_source.shops_metadata,
    }
