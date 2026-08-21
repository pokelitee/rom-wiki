from romwiki.engines.gen3.shared.constants import (
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    GROWTH_RATE_NAMES,
    ITEM_POCKET_NAMES,
    ITEM_RECORD_SIZE,
    MACHINE_COUNT,
    MACHINE_LEARNSET_SIZE,
    MAX_MOVE_ID,
    MOVE_NAME_COUNT,
    MOVE_RECORD_COUNT,
    MOVE_RECORD_SIZE,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    PERSONAL_RECORD_SIZE,
    TM_COUNT,
    TRAINER_RECORD_SIZE,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen3.shared.items import (
    item_description_pointer,
    item_name,
    parse_item_record,
)
from romwiki.engines.gen3.shared.machines import (
    machine_name,
    parse_machine_move_table,
    parse_tmhm_learnset,
)
from romwiki.engines.gen3.shared.moves import parse_move_record
from romwiki.engines.gen3.shared.personal import parse_personal_record
from romwiki.engines.gen3.shared.pointers import (
    gba_pointer_for_offset,
    resolve_gba_pointer,
)
from romwiki.engines.gen3.shared.text import (
    decode_gen3_text,
    decode_gen3_text_sequence,
    decode_gen3_text_table,
)
from romwiki.engines.gen3.shared.trainers import parse_trainer_record, party_record_size

from .constants import (
    ABILITY_NAME_COUNT,
    ITEM_NAME_COUNT,
    POKEMON_DESCRIPTION_COUNT,
    POKEMON_NAME_COUNT,
)

# `pipeline/enrichment/pokemon.py` reads these off the flat engine namespace
# without the `PERSONAL_` prefix, matching `engines/gen3/frlg/__init__.py`'s
# own INTERNAL_MEMBERS/FORM_MEMBERS aliasing convention.
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
BASE_SPECIES_COUNT = PERSONAL_RECORD_COUNT

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
    "ITEM_POCKET_NAMES",
    "ITEM_RECORD_SIZE",
    "MACHINE_COUNT",
    "MACHINE_LEARNSET_SIZE",
    "MAX_MOVE_ID",
    "MOVE_NAME_COUNT",
    "MOVE_RECORD_COUNT",
    "MOVE_RECORD_SIZE",
    "PERSONAL_FORM_MEMBERS",
    "PERSONAL_INTERNAL_MEMBERS",
    "PERSONAL_RECORD_COUNT",
    "PERSONAL_RECORD_SIZE",
    "POKEMON_DESCRIPTION_COUNT",
    "POKEMON_NAME_COUNT",
    "TM_COUNT",
    "TRAINER_RECORD_SIZE",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "decode_gen3_text",
    "decode_gen3_text_sequence",
    "decode_gen3_text_table",
    "gba_pointer_for_offset",
    "item_description_pointer",
    "item_name",
    "machine_name",
    "parse_item_record",
    "parse_machine_move_table",
    "parse_move_record",
    "parse_personal_record",
    "parse_tmhm_learnset",
    "parse_trainer_record",
    "party_record_size",
    "resolve_gba_pointer",
]
