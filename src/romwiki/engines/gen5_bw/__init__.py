from romwiki.engines.gen5_bw.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
    GEN5_BASE_SPECIES_COUNT,
    GEN5_MACHINE_COUNT,
    GEN5_MACHINE_TABLE_PREFIX,
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
    TRAINER_COSMETIC_FORM_LABELS,
    TRAINER_FORM_SLUGS,
    TYPE_NAME_COUNT,
    TYPE_NAMES,
)
from romwiki.engines.gen5_bw.egg_moves import parse_egg_move_set
from romwiki.engines.gen5_bw.encounters import (
    METHOD_NAMES as ENCOUNTER_METHOD_NAMES,
)
from romwiki.engines.gen5_bw.encounters import (
    METHOD_SLOT_CHANCES as ENCOUNTER_METHOD_SLOT_CHANCES,
)
from romwiki.engines.gen5_bw.encounters import parse_encounter_entry
from romwiki.engines.gen5_bw.evolutions import parse_evolution_record
from romwiki.engines.gen5_bw.items import parse_item_record
from romwiki.engines.gen5_bw.learnsets import parse_level_up_learnset
from romwiki.engines.gen5_bw.machines import machine_name, parse_machine_move_table
from romwiki.engines.gen5_bw.messages import parse_english_message_archive
from romwiki.engines.gen5_bw.moves import parse_move_record
from romwiki.engines.gen5_bw.personal import parse_personal_record
from romwiki.engines.gen5_bw.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen5_bw.trainers import parse_trainer_record

# EngineAdapter's shared attribute surface -- see docs/development/adding-a-game.md.
# This engine currently implements the Pokémon personal-data, Items, Moves,
# Learnsets, Evolutions, Egg moves, TM/HM machines, Wild encounters, and
# Trainers slices; the remaining EngineAdapter fields (locations, ...) all
# point at this same module per gen4_dppt's precedent, but none of their
# functions/constants exist yet. Adding a later slice should add the
# corresponding module and re-export here, the same way these slices added
# personal.py/machines.py/items.py/moves.py/learnsets.py/evolutions.py/egg_moves.py/encounters.py/trainers.py/constants.py.
# Move tutors are not a gap to fill in: Ajarmar/universal-pokemon-randomizer-zx's
# Gen5RomHandler.hasMoveTutors() returns true only for Black 2/White 2 --
# tutors were introduced in the sequels and don't exist in this release at all.
# Wild encounters don't yet attach real location names (unlike Gen4): this
# generation's map-name lookup needs its own small fixed-record table
# (`a/0/1/2`), but the map-name text table hits a text-decoder control code
# this project's message decoder doesn't handle yet -- a separate, narrow gap
# from the encounter data itself, which is fully decoded and verified.
# Trainers don't attach real map locations/script references yet either, for
# a bigger reason: this generation's script-engine opcode table (needed to
# find each trainer's battle trigger in the field) hasn't been researched.
BASE_SPECIES_COUNT = GEN5_BASE_SPECIES_COUNT
INTERNAL_MEMBERS = PERSONAL_INTERNAL_MEMBERS
FORM_MEMBERS = PERSONAL_FORM_MEMBERS
TRANSFORMATION_MEMBERS = PERSONAL_TRANSFORMATION_MEMBERS
MACHINE_COUNT = GEN5_MACHINE_COUNT

__all__ = [
    "ABILITY_NAME_COUNT",
    "BASE_SPECIES_COUNT",
    "COLOR_NAMES",
    "DAMAGE_CLASS_NAMES",
    "EGG_GROUP_NAMES",
    "ENCOUNTER_METHOD_NAMES",
    "ENCOUNTER_METHOD_SLOT_CHANCES",
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
    "FORM_MEMBERS",
    "GEN5_BASE_SPECIES_COUNT",
    "GEN5_MACHINE_TABLE_PREFIX",
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
    "TRAINER_COSMETIC_FORM_LABELS",
    "TRAINER_FORM_SLUGS",
    "TRANSFORMATION_MEMBERS",
    "TYPE_NAME_COUNT",
    "TYPE_NAMES",
    "derive_trainer_party_attributes",
    "machine_name",
    "normalize_trainer_party_member",
    "parse_egg_move_set",
    "parse_encounter_entry",
    "parse_english_message_archive",
    "parse_evolution_record",
    "parse_item_record",
    "parse_level_up_learnset",
    "parse_machine_move_table",
    "parse_move_record",
    "parse_personal_record",
    "parse_trainer_record",
]
