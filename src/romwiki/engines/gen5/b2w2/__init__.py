"""Pokémon Black 2 and White 2 engine-specific record support."""

from .constants import (
    GEN5_BASE_SPECIES_COUNT,
    GEN5_ITEM_FIELD_USE_NAMES,
    GEN5_MACHINE_COUNT,
    ITEM_NAME_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_RECORD_SIZE,
    PERSONAL_TRANSFORMATION_MEMBERS,
    POKEMON_NAME_COUNT,
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
)
from .disassembler import disassemble_function, parse_function_offsets
from .locations import (
    COMMON_SCRIPT_MEMBER_BASE,
    NPC_TRADE_INTERACTION_BY_ID,
    NPC_TRADE_TEXT_MEMBER_BY_ID,
    WARP_DESTINATION_INDEXED,
    parse_map_header_script_files,
    parse_map_header_table,
    parse_map_header_text_files,
    parse_wild_map_names,
    resolve_common_script_member,
)
from .marts import (
    SHOP_SELECTOR_TO_INVENTORY_ID,
    parse_archive_shop_catalog,
    resolve_location_special_vendors,
    resolve_special_vendor,
)
from .personal import parse_personal_record
from .static_encounters import discover_static_encounters, find_fossil_revival_script
from .tutors import (
    TUTOR_COMPATIBILITY_OFFSET,
    TUTOR_COUNT,
    TUTOR_LOCATION_NAMES,
    TUTOR_RECORD_SIZE,
    parse_tutor_compatibility_record,
    parse_tutor_move_table,
)

BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT
ITEM_FIELD_USE_NAMES = GEN5_ITEM_FIELD_USE_NAMES

__all__ = [
    "BASE_SPECIES_COUNT",
    "COMMON_SCRIPT_MEMBER_BASE",
    "FORM_MEMBERS",
    "GEN5_BASE_SPECIES_COUNT",
    "GEN5_ITEM_FIELD_USE_NAMES",
    "GEN5_MACHINE_COUNT",
    "INTERNAL_MEMBERS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
    "NPC_TRADE_INTERACTION_BY_ID",
    "NPC_TRADE_TEXT_MEMBER_BY_ID",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "PERSONAL_TRANSFORMATION_MEMBERS",
    "POKEMON_NAME_COUNT",
    "SHOP_SELECTOR_TO_INVENTORY_ID",
    "TUTOR_COMPATIBILITY_OFFSET",
    "TUTOR_COUNT",
    "TUTOR_LOCATION_NAMES",
    "TUTOR_RECORD_SIZE",
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TRANSFORMATION_MEMBERS",
    "WARP_DESTINATION_INDEXED",
    "discover_static_encounters",
    "find_fossil_revival_script",
    "disassemble_function",
    "parse_personal_record",
    "parse_map_header_script_files",
    "parse_map_header_text_files",
    "parse_map_header_table",
    "parse_function_offsets",
    "parse_archive_shop_catalog",
    "parse_tutor_compatibility_record",
    "parse_tutor_move_table",
    "parse_wild_map_names",
    "resolve_common_script_member",
    "resolve_location_special_vendors",
    "resolve_special_vendor",
]
