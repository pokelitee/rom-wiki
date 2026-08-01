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
from .locations import (
    WARP_DESTINATION_INDEXED,
    parse_map_header_script_files,
    parse_map_header_table,
    parse_wild_map_names,
)
from .marts import SHOP_SELECTOR_TO_INVENTORY_ID, parse_archive_shop_catalog
from .personal import parse_personal_record
from .static_encounters import discover_static_encounters
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
    "FORM_MEMBERS",
    "GEN5_BASE_SPECIES_COUNT",
    "GEN5_ITEM_FIELD_USE_NAMES",
    "GEN5_MACHINE_COUNT",
    "INTERNAL_MEMBERS",
    "ITEM_FIELD_USE_NAMES",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
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
    "parse_personal_record",
    "parse_map_header_script_files",
    "parse_map_header_table",
    "parse_archive_shop_catalog",
    "parse_tutor_compatibility_record",
    "parse_tutor_move_table",
    "parse_wild_map_names",
]
