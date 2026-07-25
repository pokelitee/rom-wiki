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
from romwiki.engines.gen5_bw.locations import (
    parse_map_header_table,
    parse_wild_map_names,
)
from romwiki.engines.gen5_bw.machines import machine_name, parse_machine_move_table
from romwiki.engines.gen5_bw.messages import parse_english_message_archive
from romwiki.engines.gen5_bw.moves import parse_move_record
from romwiki.engines.gen5_bw.personal import parse_personal_record
from romwiki.engines.gen5_bw.trades import parse_npc_trade_record
from romwiki.engines.gen5_bw.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.engines.gen5_bw.trainers import parse_trainer_record

# EngineAdapter's shared attribute surface -- see docs/development/adding-a-game.md.
# This engine currently implements the Pokémon personal-data, Items, Moves,
# Learnsets, Evolutions, Egg moves, TM/HM machines, Wild encounters, Trainers,
# and (a bare-minimum) Locations slices. Adding a later slice should add the
# corresponding module and re-export here, the same way these slices added
# personal.py/machines.py/items.py/moves.py/learnsets.py/evolutions.py/egg_moves.py/encounters.py/trainers.py/locations.py/constants.py.
# Move tutors are not a gap to fill in: Ajarmar/universal-pokemon-randomizer-zx's
# Gen5RomHandler.hasMoveTutors() returns true only for Black 2/White 2 --
# tutors were introduced in the sequels and don't exist in this release at all.
# Wild encounters attach real display names via `locations.py`'s small
# fixed-record map header table (`a/0/1/2`) -- messages.py's `_VARIABLE_MARKER`
# handling was needed first, since one (unused) entry in the map-name table
# contains a runtime-substituted-text control code that used to make the
# whole table fail to decode.
# Locations is deliberately a bare minimum: just each map header's display
# name and its wild-encounter-table cross-reference, both of which the
# randomizer community's own code already uses (so they're verifiable
# against Gen5RomHandler.java). No public reference documents the rest of
# the 48-byte map header record (warps, connections, scripts, music, ...),
# and this generation's own script-engine opcode table -- which Trainers'
# location/script-reference linking also needs -- hasn't been researched;
# guessing at either isn't done here.
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
    "parse_map_header_table",
    "parse_move_record",
    "parse_personal_record",
    "parse_npc_trade_record",
    "parse_trainer_record",
    "parse_wild_map_names",
]
