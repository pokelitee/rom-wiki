from romwiki.engines.gen5_bw.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    EGG_GROUP_NAMES,
    GEN5_BASE_SPECIES_COUNT,
    GEN5_MACHINE_COUNT,
    GROWTH_RATE_NAMES,
    ITEM_NAME_COUNT,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_TRANSFORMATION_MEMBERS,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen5_bw.items import parse_item_record
from romwiki.engines.gen5_bw.machines import machine_name
from romwiki.engines.gen5_bw.messages import parse_english_message_archive
from romwiki.engines.gen5_bw.personal import parse_personal_record

# EngineAdapter's shared attribute surface -- see docs/development/adding-a-game.md.
# This engine currently implements only the Pokémon personal-data and Items
# slices; the remaining EngineAdapter fields (locations, trainers, encounters,
# ...) all point at this same module per gen4_dppt's precedent, but none of
# their functions/constants exist yet. Adding a later slice (moves, trainers,
# ...) should add the corresponding module and re-export here, the same way
# these slices added personal.py/machines.py/items.py/constants.py.
BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT

__all__ = [
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "COLOR_NAMES",
    "EGG_GROUP_NAMES",
    "FORM_MEMBERS",
    "GEN5_BASE_SPECIES_COUNT",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "ITEM_NAME_COUNT",
    "MACHINE_COUNT",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_TRANSFORMATION_MEMBERS",
    "POKEMON_NAME_COUNT",
    "TRANSFORMATION_MEMBERS",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "machine_name",
    "parse_english_message_archive",
    "parse_item_record",
    "parse_personal_record",
]
