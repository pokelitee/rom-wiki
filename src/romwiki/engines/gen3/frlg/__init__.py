from .constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    EGG_GROUP_NAMES,
    GROWTH_RATE_NAMES,
    ITEM_NAME_COUNT,
    MOVE_NAME_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_RECORD_SIZE,
    POKEMON_DESCRIPTION_COUNT,
    POKEMON_NAME_COUNT,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from .personal import parse_personal_record

# `pipeline/enrichment/pokemon.py` reads these off the flat engine namespace
# without the `PERSONAL_` prefix, matching `engines/gen5/bw/__init__.py`'s
# own INTERNAL_MEMBERS/FORM_MEMBERS aliasing convention.
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS

__all__ = [
    "ABILITY_NAME_COUNT",
    "COLOR_NAMES",
    "EGG_GROUP_NAMES",
    "FORM_MEMBERS",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "ITEM_NAME_COUNT",
    "MOVE_NAME_COUNT",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "POKEMON_DESCRIPTION_COUNT",
    "POKEMON_NAME_COUNT",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "parse_personal_record",
]
