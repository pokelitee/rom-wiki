from romwiki.engines.gen4.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    GEN4_MAX_FRIENDSHIP,
    GROWTH_RATE_NAMES,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    NATURAL_GIFT_TYPE_NONE,
    PERSONAL_RECORD_COUNT,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen4.egg_moves import parse_egg_move_table
from romwiki.engines.gen4.events import (
    parse_map_events,
    parse_object_events,
    parse_warp_events,
    resolve_hidden_item_id,
    resolve_visible_item_id,
)
from romwiki.engines.gen4.evolutions import parse_evolution_record
from romwiki.engines.gen4.items import (
    GEN4_ITEM_FIELD_USE_NAMES,
    GEN4_ITEM_POCKET_NAMES,
    find_item_archive_members,
    parse_item_record,
)
from romwiki.engines.gen4.learnsets import parse_level_up_learnset
from romwiki.engines.gen4.machines import (
    GEN4_MACHINE_COUNT,
    GEN4_TM_COUNT,
    machine_name,
    parse_machine_move_table,
)
from romwiki.engines.gen4.map_matrices import parse_map_matrix
from romwiki.engines.gen4.messages import parse_english_message_archive
from romwiki.engines.gen4.moves import MOVE_RECORD_SIZE, parse_move_record
from romwiki.engines.gen4.personal import (
    GEN4_BASE_SPECIES_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_SIZE,
    TRAINER_COSMETIC_FORM_LABELS,
    parse_personal_record,
)
from romwiki.engines.gen4.personal import (
    TRAINER_FORM_SLUGS as GEN4_TRAINER_FORM_SLUGS,
)
from romwiki.engines.gen4.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen4.trainers import (
    parse_trainer_class_genders,
    parse_trainer_class_prize_multipliers,
    parse_trainer_record,
)

from .battle_variants import extract_trainer_battle_families
from .encounters import (
    HGSS_FISHING_SLOT_CHANCES,
    HGSS_ROCK_SMASH_SLOT_CHANCES,
    HGSS_WALKING_SLOT_CHANCES,
    HGSS_WATER_SLOT_CHANCES,
    parse_encounter_record,
)
from .map_headers import MAP_HEADER_SIZE, parse_map_headers
from .marts import parse_shop_catalog
from .pickup import (
    PICKUP_COMMON_ITEM_COUNT,
    PICKUP_COMMON_TABLE_LOCATOR,
    PICKUP_LEVEL_RANGE_COUNT,
    PICKUP_LEVEL_RANGE_SIZE,
    PICKUP_RARE_ITEM_COUNT,
    PICKUP_RARE_TABLE_LOCATOR,
    PICKUP_SLOT_CHANCES,
    parse_pickup_item_table,
    pickup_level_range_item_ids,
)
from .trades import NPC_TRADE_RECORD_SIZE, parse_npc_trade_record
from .tutors import (
    TUTOR_COMPATIBILITY_RECORD_SIZE,
    TUTOR_COUNT,
    TUTOR_LOCATION_NAMES,
    TUTOR_RECORD_SIZE,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)

parse_map_header_table = parse_map_headers

BASE_SPECIES_COUNT = GEN4_BASE_SPECIES_COUNT
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
MACHINE_COUNT = GEN4_MACHINE_COUNT
MAX_FRIENDSHIP = GEN4_MAX_FRIENDSHIP
ITEM_NAME_COUNT = 537
ITEM_POCKET_NAMES = GEN4_ITEM_POCKET_NAMES
ITEM_FIELD_USE_NAMES = GEN4_ITEM_FIELD_USE_NAMES + (
    "unown-report",
    "dowsing-machine",
    "gb-sounds",
    "gracidea",
    "vs-recorder",
)
MACHINE_TABLE_LOCATOR = "1E003200"
CODE_BINARY_DECOMPRESSED = True
ARCHIVE_MEMBER_NONE = 0
ENCOUNTER_MEMBER_NONE = 0xFF
MATRIX_VOID_HEADER_IDS = frozenset((0, 0xFFFF))
DYNAMIC_WARP_HEADER_ID = 0xFFF
DYNAMIC_WARP_ID = 0x100
WALKING_SLOT_CHANCES = HGSS_WALKING_SLOT_CHANCES
WATER_SLOT_CHANCES = HGSS_WATER_SLOT_CHANCES
FISHING_SLOT_CHANCES = HGSS_FISHING_SLOT_CHANCES
ROCK_SMASH_SLOT_CHANCES = HGSS_ROCK_SMASH_SLOT_CHANCES
FIRST_TRAINER_ID = 1
TRAINER_LOCATION_EXTRACTION = True
TRAINER_SCRIPT_REFERENCE_EXTRACTION = False
TRAINER_OBJECT_SCRIPT_START = 3000
TRAINER_OBJECT_SCRIPT_END = 3999
TRAINER_OBJECT_ID_OFFSET = 1
ALLOW_DUPLICATE_EGG_MOVES = True
# Sacred Gold and Storm Silver v1.05 both store form bits 1 on trainer 229's
# Pinsir. Pinsir has no Generation IV form, so retain the raw form ID while
# resolving its display/reference target to the base species.
TRAINER_FORM_SLUGS = {**GEN4_TRAINER_FORM_SLUGS, (127, 1): "pinsir"}

__all__ = [
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "FORM_MEMBERS",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
    "MAX_FRIENDSHIP",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "MOVE_RECORD_SIZE",
    "NATURAL_GIFT_TYPE_NONE",
    "NPC_TRADE_RECORD_SIZE",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "PICKUP_COMMON_ITEM_COUNT",
    "PICKUP_COMMON_TABLE_LOCATOR",
    "PICKUP_LEVEL_RANGE_COUNT",
    "PICKUP_LEVEL_RANGE_SIZE",
    "PICKUP_RARE_ITEM_COUNT",
    "PICKUP_RARE_TABLE_LOCATOR",
    "PICKUP_SLOT_CHANCES",
    "POKEMON_NAME_COUNT",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "TUTOR_COMPATIBILITY_RECORD_SIZE",
    "TUTOR_COUNT",
    "TUTOR_LOCATION_NAMES",
    "TUTOR_RECORD_SIZE",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_POCKET_NAMES",
    "MACHINE_TABLE_LOCATOR",
    "GEN4_TM_COUNT",
    "MAP_HEADER_SIZE",
    "parse_egg_move_table",
    "parse_encounter_record",
    "parse_evolution_record",
    "parse_item_record",
    "find_item_archive_members",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_map_headers",
    "parse_map_header_table",
    "parse_map_matrix",
    "parse_shop_catalog",
    "parse_map_events",
    "parse_object_events",
    "parse_warp_events",
    "resolve_hidden_item_id",
    "resolve_visible_item_id",
    "parse_trainer_class_genders",
    "parse_trainer_class_prize_multipliers",
    "parse_trainer_record",
    "parse_npc_trade_record",
    "parse_tutor_compatibility_table",
    "parse_tutor_move_table",
    "derive_trainer_party_attributes",
    "extract_trainer_battle_families",
    "normalize_trainer_party_member",
    "machine_name",
    "parse_personal_record",
    "parse_pickup_item_table",
    "pickup_level_range_item_ids",
    "parse_english_message_archive",
    "parse_move_record",
]
