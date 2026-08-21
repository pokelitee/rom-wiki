from romwiki.engines.gen3.shared.battle_variants import resolve_trainer_variants
from romwiki.engines.gen3.shared.constants import (
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    ENCOUNTER_FISHING_SLOT_CHANCES,
    ENCOUNTER_FISHING_SLOT_COUNT,
    ENCOUNTER_HEADER_SIZE,
    ENCOUNTER_LAND_SLOT_CHANCES,
    ENCOUNTER_LAND_SLOT_COUNT,
    ENCOUNTER_METHOD_NAMES,
    ENCOUNTER_ROCK_SMASH_SLOT_CHANCES,
    ENCOUNTER_ROCK_SMASH_SLOT_COUNT,
    ENCOUNTER_WATER_SLOT_CHANCES,
    ENCOUNTER_WATER_SLOT_COUNT,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    EVOLUTION_RECORD_SIZE,
    EVOLUTION_SLOT_COUNT,
    EVOLUTION_SLOT_SIZE,
    FIRST_MACHINE_ITEM_ID,
    GROWTH_RATE_NAMES,
    INTERNAL_TO_NATIONAL_DEX,
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
from romwiki.engines.gen3.shared.egg_moves import parse_egg_move_table
from romwiki.engines.gen3.shared.encounters import (
    parse_encounter_record,
    parse_header,
    parse_method_info,
    parse_method_slots,
)
from romwiki.engines.gen3.shared.evolutions import parse_evolution_record
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
from romwiki.engines.gen3.shared.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen3.shared.trainers import parse_trainer_record, party_record_size

from .constants import (
    ABILITY_NAME_COUNT,
    ENCOUNTER_HEADER_COUNT,
    ITEM_NAME_COUNT,
    ITEM_RECORD_COUNT,
    POKEMON_DESCRIPTION_COUNT,
    POKEMON_NAME_COUNT,
    TRAINER_RECORD_COUNT,
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
    "ENCOUNTER_FISHING_SLOT_CHANCES",
    "ENCOUNTER_FISHING_SLOT_COUNT",
    "ENCOUNTER_HEADER_COUNT",
    "ENCOUNTER_HEADER_SIZE",
    "ENCOUNTER_LAND_SLOT_CHANCES",
    "ENCOUNTER_LAND_SLOT_COUNT",
    "ENCOUNTER_METHOD_NAMES",
    "ENCOUNTER_ROCK_SMASH_SLOT_CHANCES",
    "ENCOUNTER_ROCK_SMASH_SLOT_COUNT",
    "ENCOUNTER_WATER_SLOT_CHANCES",
    "ENCOUNTER_WATER_SLOT_COUNT",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "EVOLUTION_RECORD_SIZE",
    "EVOLUTION_SLOT_COUNT",
    "EVOLUTION_SLOT_SIZE",
    "FIRST_MACHINE_ITEM_ID",
    "FORM_MEMBERS",
    "GROWTH_RATE_NAMES",
    "INTERNAL_MEMBERS",
    "INTERNAL_TO_NATIONAL_DEX",
    "ITEM_NAME_COUNT",
    "ITEM_POCKET_NAMES",
    "ITEM_RECORD_COUNT",
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
    "TRAINER_RECORD_COUNT",
    "TRAINER_RECORD_SIZE",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "decode_gen3_text",
    "decode_gen3_text_sequence",
    "decode_gen3_text_table",
    "derive_trainer_party_attributes",
    "gba_pointer_for_offset",
    "item_description_pointer",
    "item_name",
    "machine_name",
    "normalize_trainer_party_member",
    "parse_egg_move_table",
    "parse_encounter_record",
    "parse_evolution_record",
    "parse_header",
    "parse_item_record",
    "parse_machine_move_table",
    "parse_method_info",
    "parse_method_slots",
    "parse_move_record",
    "parse_personal_record",
    "parse_tmhm_learnset",
    "parse_trainer_record",
    "party_record_size",
    "resolve_gba_pointer",
    "resolve_trainer_variants",
]
