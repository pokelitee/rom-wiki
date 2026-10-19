"""Typed contracts for the namespaces an engine adapter exposes to the pipeline.

Each protocol lists every member shared pipeline code reads from one concern.
A member that only some engines provide is read only behind the semantic
format, dataset kind, or capability that requires it; registry validation
checks those requirements when an engine is registered. Parsers return
engine-specific record types, so they are typed by name rather than signature.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

Parser = Callable[..., Any]
FormLabels = Mapping[tuple[int, int], str]


class PersonalConcern(Protocol):
    ABILITY_NAME_COUNT: int
    ITEM_RECORD_SIZE: int
    MACHINE_LEARNSET_SIZE: int
    PERSONAL_RECORD_COUNT: int
    PERSONAL_RECORD_SIZE: int
    decode_gen3_text: Parser
    decode_gen3_name_table: Parser
    parse_personal_record: Parser
    resolve_gba_pointer: Parser


class MessageArchiveReader(Protocol):
    parse_english_message_archive: Parser


class LocationConcern(MessageArchiveReader, Protocol):
    ARCHIVE_MEMBER_NONE: int
    DYNAMIC_WARP_HEADER_ID: int
    DYNAMIC_WARP_ID: int
    ENCOUNTER_MEMBER_NONE: int
    FIRST_REGION_MAP_SECTION: int
    GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID: int
    GMAPGROUPS_GROUP_COUNT: int
    GREAT_MARSH_HEADER_IDS: tuple[int, ...]
    GREAT_MARSH_POST_NATIONAL_DEX_MEMBER: int
    GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER: int
    HONEY_TREE_COMMON_MEMBER: int
    HONEY_TREE_HEADER_IDS: tuple[int, ...]
    HONEY_TREE_RARE_MEMBER: int
    HONEY_TREE_UNCOMMON_MEMBER: int
    ITEM_BALL_TABLE_SCRIPT_MEMBER: int
    MAP_HEADER_SIZE: int
    MATRIX_VOID_HEADER_IDS: frozenset[int]
    NPC_TRADE_TEXT_MEMBER_BY_ID: Mapping[int, int]
    REGION_NAME_ENTRY_SIZE: int
    REGION_NAME_POINTER_OFFSET: int
    ROAMING_SLOT_COUNT: int
    ROAMING_SLOT_SPECIES_IDS: tuple[int, ...]
    TROPHY_GARDEN_HEADER_ID: int
    TROPHY_GARDEN_MEMBER: int
    WARP_DESTINATION_INDEXED: bool
    decode_gen3_name: Parser
    disassemble_function: Parser
    find_item_archive_members: Parser
    find_script_awarded_items: Parser
    is_hidden_item_candidate: Parser
    is_visible_item_candidate: Parser
    parse_common_mart_inventory: Parser
    parse_decoration_price_table: Parser
    parse_egg_gift_commands: Parser
    parse_frontier_price_table: Parser
    parse_function_offsets: Parser
    parse_game_corner_prizes: Parser
    parse_hidden_item_table: Parser
    parse_item_ball_table: Parser
    parse_item_price: Parser
    parse_gmapgroups_pointers: Parser
    parse_map_events: Parser
    parse_map_group_index: Parser
    parse_map_header_script_files: Parser
    parse_map_header_table: Parser
    parse_map_headers: Parser
    parse_map_header_text_files: Parser
    parse_map_matrix: Parser
    parse_mart_commands: Parser
    parse_mart_dispatch_commands: Parser
    parse_npc_trade_commands: Parser
    parse_npc_trade_record: Parser
    parse_overworld_furniture: Parser
    parse_overworld_npcs: Parser
    parse_pokemon_gift_commands: Parser
    parse_roaming_activation_commands: Parser
    parse_seal_price_table: Parser
    parse_specialty_mart_inventories: Parser
    parse_species_list: Parser
    parse_static_encounter_commands: Parser
    parse_togepi_egg_gift_commands: Parser
    resolve_common_script_member: Parser
    resolve_hidden_item_id: Parser
    resolve_location_special_vendors: Parser
    resolve_visible_item_id: Parser
    shop_schedule_label: Parser
    trade_language_name: Parser


class TrainerConcern(MessageArchiveReader, Protocol):
    ARCHIVE_MEMBER_NONE: int
    BASE_SPECIES_COUNT: int
    CHECK_WON_BATTLE: int
    FIRST_TRAINER_ID: int
    MAP_HEADER_SIZE: int
    REMATCH_RECORD_SIZE: int
    STARTER_SPECIES_ENTRY_SIZE: int
    START_TRAINER_BATTLE: int
    TRAINER_OBJECT_ID_OFFSET: int
    TRAINER_OBJECT_SCRIPT_END: int
    TRAINER_OBJECT_SCRIPT_START: int
    TRAINER_RECORD_COUNT: int
    TRAINER_RECORD_SIZE: int
    decode_gen3_name: Parser
    parse_difficulty_branch_families: Parser
    parse_map_header: Parser
    parse_map_header_script_files: Parser
    parse_map_header_table: Parser
    parse_map_headers: Parser
    parse_object_events: Parser
    parse_overworld_npcs: Parser
    parse_rematch_table: Parser
    parse_staged_partner_battle_families: Parser
    parse_starter_branch_families: Parser
    parse_starter_species: Parser
    parse_tag_battle_commands: Parser
    parse_trainer_battle_commands: Parser
    parse_trainer_class_genders: Parser
    parse_trainer_class_prize_multipliers: Parser
    parse_trainer_record: Parser
    party_record_size: Parser
    resolve_common_script_trainer_id: Parser
    resolve_gba_pointer: Parser
    resolve_trainer_variants: Parser
    trainer_name_index: Parser


class EncounterConcern(MessageArchiveReader, Protocol):
    ARCHIVE_MEMBER_NONE: int
    ENCOUNTER_COSMETIC_FORM_LABELS: FormLabels
    ENCOUNTER_FISHING_SLOT_COUNT: int
    ENCOUNTER_FORM_SLUGS: FormLabels
    ENCOUNTER_HEADER_SIZE: int
    ENCOUNTER_LAND_SLOT_COUNT: int
    ENCOUNTER_METHOD_NAMES: tuple[str, ...]
    ENCOUNTER_ROCK_SMASH_SLOT_COUNT: int
    ENCOUNTER_WATER_SLOT_COUNT: int
    GMAPGROUPS_GROUP_COUNT: int
    ITEM_NAME_COUNT: int
    MAP_HEADER_SIZE: int
    POKEMON_NAME_COUNT: int
    SAFARI_AREA_NAMES: tuple[str, ...]
    SWARM_RECORD_SIZE: int
    decode_gen3_name: Parser
    gba_pointer_for_offset: Parser
    hidden_grotto_id_for_dispatch: Parser
    parse_encounter_entry: Parser
    parse_encounter_record: Parser
    parse_gmapgroups_pointers: Parser
    parse_headbutt_record: Parser
    parse_header: Parser
    parse_hidden_grotto_record: Parser
    parse_map_group_index: Parser
    parse_map_header: Parser
    parse_map_header_table: Parser
    parse_map_headers: Parser
    parse_method_info: Parser
    parse_method_slots: Parser
    parse_overworld_furniture: Parser
    parse_safari_encounter_record: Parser
    parse_swarm_table: Parser
    parse_wild_map_names: Parser
    resolve_gba_pointer: Parser


class EvolutionConcern(MessageArchiveReader, Protocol):
    EVOLUTION_RECORD_SIZE: int
    ITEM_RECORD_COUNT: int
    ITEM_RECORD_SIZE: int
    PERSONAL_RECORD_COUNT: int
    decode_gen3_name_table: Parser
    parse_evolution_record: Parser


class ItemConcern(MessageArchiveReader, Protocol):
    BERRY_FIRMNESS_NAMES: Mapping[int, str]
    ITEM_FIELD_USE_NAMES: tuple[str, ...]
    ITEM_POCKET_NAMES: tuple[str, ...]
    ITEM_RECORD_COUNT: int
    ITEM_RECORD_SIZE: int
    NATURAL_GIFT_TYPE_NONE: int
    POKEMON_NAME_COUNT: int
    decode_gen3_text: Parser
    find_fossil_revival_script: Parser
    find_item_archive_members: Parser
    item_description_pointer: Parser
    item_name: Parser
    parse_berry_record: Parser
    parse_fossil_revival_table: Parser
    parse_item_record: Parser
    resolve_gba_pointer: Parser


class MachineConcern(Protocol):
    MACHINE_COUNT: int
    MACHINE_TABLE_LOCATOR: str
    #: Default TM count for the profile-offset table format, whose machine
    #: numbering is split between TMs and HMs at this index.
    TM_COUNT: int
    parse_machine_move_table: Parser


class MoveConcern(Protocol):
    MOVE_RECORD_COUNT: int
    MOVE_RECORD_SIZE: int
    decode_gen3_name_table: Parser
    parse_move_record: Parser


class TutorConcern(Protocol):
    BASE_SPECIES_COUNT: int
    FORM_MEMBERS: Mapping[int, str]
    MAP_HEADER_SIZE: int
    MAX_FRIENDSHIP: int
    PERSONAL_RECORD_COUNT: int
    TUTOR_COMPATIBILITY_OFFSET: int
    TUTOR_COMPATIBILITY_RECORD_SIZE: int
    TUTOR_COMPATIBILITY_SIZE: int
    TUTOR_COUNT: int
    TUTOR_LOCATIONS: Mapping[int, str]
    TUTOR_LOCATION_NAMES: tuple[str, ...]
    TUTOR_MOVE_COUNT: int
    TUTOR_RECORD_SIZE: int
    decode_gen3_name: Parser
    parse_english_message_archive: Parser
    parse_map_header: Parser
    parse_personal_record: Parser
    parse_special_tutor_move: Parser
    parse_special_tutor_species: Parser
    parse_tutor_compatibility: Parser
    parse_tutor_compatibility_record: Parser
    parse_tutor_compatibility_table: Parser
    parse_tutor_move_table: Parser


class EggMoveConcern(Protocol):
    parse_egg_move_set: Parser
    parse_egg_move_table: Parser


class LearnsetConcern(Protocol):
    LEARNSET_POINTER_SIZE: int
    LEARNSET_READ_SIZE: int
    parse_level_up_learnset: Parser
    resolve_gba_pointer: Parser


class ReferenceNameConcern(MessageArchiveReader, Protocol):
    ABILITY_NAME_COUNT: int
    ITEM_NAME_COUNT: int
    MOVE_NAME_COUNT: int
    POKEMON_DESCRIPTION_COUNT: int | None
    POKEMON_NAME_COUNT: int
    TYPE_NAME_COUNT: int


class EnrichmentTables(Protocol):
    ABILITY_NAME_COUNT: int
    ABILITY_REFERENCE_IDS: Mapping[int, int | None]
    ALLOW_DUPLICATE_EGG_MOVES: bool
    BASE_SPECIES_COUNT: int
    COLOR_NAMES: tuple[str, ...]
    DAMAGE_CLASS_NAMES: tuple[str, ...]
    EGG_GROUP_NAMES: tuple[str, ...]
    ENCOUNTER_COSMETIC_FORM_LABELS: FormLabels
    ENCOUNTER_FORM_SLUGS: FormLabels
    EVOLUTION_METHOD_NAMES: tuple[str, ...]
    EVOLUTION_PARAMETER_KINDS: Mapping[int, str]
    FORM_MEMBERS: Mapping[int, str]
    GROWTH_RATE_NAMES: tuple[str, ...]
    INTERNAL_MEMBERS: Mapping[int, str]
    INTERNAL_TO_NATIONAL_DEX: Mapping[int, int]
    ITEM_NAME_COUNT: int
    MACHINE_COUNT: int
    MAX_MOVE_ID: int
    MOVE_NAME_COUNT: int
    MOVE_RECORD_COUNT: int
    PERSONAL_RECORD_COUNT: int
    POKEMON_DESCRIPTION_COUNT: int | None
    POKEMON_NAME_COUNT: int
    TRAINER_COSMETIC_FORM_LABELS: FormLabels
    TRAINER_FORM_SLUGS: FormLabels
    TRANSFORMATION_MEMBERS: Mapping[int, Mapping[str, str]]
    TYPE_NAME_COUNT: int
    TYPE_NAMES: tuple[str, ...]
    machine_name: Parser
    # Conditional-encounter slot tables.
    BONUS_SLOT_METHODOLOGY_SOURCE: str
    DUAL_SLOT_SLOT_INDICES: tuple[int, ...]
    FISHING_SLOT_CHANCES: tuple[int, ...]
    ROCK_SMASH_SLOT_CHANCES: tuple[int, ...]
    SWARM_SLOT_INDICES: tuple[int, ...]
    TIMED_SLOT_INDICES: tuple[int, ...]
    UNOWN_FORM_NAMES: tuple[str, ...]
    UNOWN_FORM_TABLES: tuple[tuple[int, ...], ...]
    WALKING_SLOT_CHANCES: tuple[int, ...]
    WATER_SLOT_CHANCES: tuple[int, ...]
    # Seasonal-encounter slot tables.
    ENCOUNTER_METHOD_NAMES: tuple[str, ...]
    ENCOUNTER_METHOD_SLOT_CHANCES: tuple[tuple[int, ...], ...]
    # Method-table encounter slot tables.
    ENCOUNTER_FISHING_SLOT_CHANCES: tuple[int, ...]
    ENCOUNTER_LAND_SLOT_CHANCES: tuple[int, ...]
    ENCOUNTER_ROCK_SMASH_SLOT_CHANCES: tuple[int, ...]
    ENCOUNTER_WATER_SLOT_CHANCES: tuple[int, ...]


class TrainerPartyConcern(Protocol):
    derive_trainer_party_attributes: Parser
    normalize_trainer_party_member: Parser


class TradeConcern(MessageArchiveReader, Protocol):
    #: Interaction labels keyed by trade ID; empty when every trade is a plain
    #: in-person exchange.
    NPC_TRADE_INTERACTION_BY_ID: Mapping[int, str]
    parse_npc_trade_record: Parser


class MartConcern(MessageArchiveReader, Protocol):
    parse_archive_shop_catalog: Parser
    parse_shop_catalog: Parser


class StaticEncounterConcern(Protocol):
    ITEM_NAME_COUNT: int
    POKEMON_NAME_COUNT: int
    discover_static_encounters: Parser


class PickupConcern(MessageArchiveReader, Protocol):
    PICKUP_COMMON_ITEM_COUNT: int
    PICKUP_COMMON_RATE_COUNT: int
    PICKUP_COMMON_TABLE_LOCATOR: str
    PICKUP_HONEY_GATHER_RATE_COUNT: int
    PICKUP_LEVEL_RANGE_COUNT: int
    PICKUP_LEVEL_RANGE_SIZE: int
    PICKUP_RARE_ITEM_COUNT: int
    PICKUP_RARE_TABLE_LOCATOR: str
    PICKUP_SLOT_CHANCES: tuple[int, ...]
    PICKUP_TABLE_LOCATOR: str
    parse_pickup_item_table: Parser
    parse_pickup_table: Parser
    parse_pickup_tables: Parser
    pickup_level_range_item_ids: Parser
