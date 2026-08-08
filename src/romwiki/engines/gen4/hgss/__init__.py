from romwiki.engines.gen4.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    GEN4_MAX_FRIENDSHIP,
    GROWTH_RATE_NAMES,
    ITEM_NAME_COUNT,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    PERSONAL_RECORD_COUNT,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen4.machines import GEN4_MACHINE_COUNT, machine_name
from romwiki.engines.gen4.messages import parse_english_message_archive
from romwiki.engines.gen4.moves import MOVE_RECORD_SIZE, parse_move_record
from romwiki.engines.gen4.personal import (
    GEN4_BASE_SPECIES_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_SIZE,
    parse_personal_record,
)

BASE_SPECIES_COUNT = GEN4_BASE_SPECIES_COUNT
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
MACHINE_COUNT = GEN4_MACHINE_COUNT
MAX_FRIENDSHIP = GEN4_MAX_FRIENDSHIP

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
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "POKEMON_NAME_COUNT",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "machine_name",
    "parse_personal_record",
    "parse_english_message_archive",
    "parse_move_record",
]
