from romwiki.engines.gen5_bw.constants import (
    ABILITY_NAME_COUNT,
    COLOR_NAMES,
    DAMAGE_CLASS_NAMES,
    EGG_GROUP_NAMES,
    EVOLUTION_METHOD_NAMES,
    EVOLUTION_PARAMETER_KINDS,
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
from romwiki.engines.gen5_bw.evolutions import parse_evolution_record
from romwiki.engines.gen5_bw.items import parse_item_record
from romwiki.engines.gen5_bw.learnsets import parse_level_up_learnset
from romwiki.engines.gen5_bw.machines import machine_name
from romwiki.engines.gen5_bw.messages import parse_english_message_archive
from romwiki.engines.gen5_bw.moves import parse_move_record
from romwiki.engines.gen5_bw.personal import parse_personal_record

# EngineAdapter's shared attribute surface -- see docs/development/adding-a-game.md.
# This engine currently implements the Pokémon personal-data, Items, Moves,
# Learnsets, and Evolutions slices; the remaining EngineAdapter fields
# (locations, trainers, encounters, ...) all point at this same module per
# gen4_dppt's precedent, but none of their functions/constants exist yet.
# Adding a later slice should add the corresponding module and re-export
# here, the same way these slices added
# personal.py/machines.py/items.py/moves.py/learnsets.py/evolutions.py/constants.py.
# Egg moves, tutors, and TM/HM move assignments are deliberately not
# implemented yet: Egg moves need a provenance-shape generalization shared
# with gen4_dppt (its Gen4EggMoveSet models a flat ARM9-overlay table with a
# byte offset, not this generation's per-species NARC archive); tutors and
# machines need this generation's compressed-ARM9 move table located via a
# byte-pattern search this codebase doesn't implement yet (see
# Gen5RomHandler.java's `getTMMoves`/tmDataPrefix in
# Ajarmar/universal-pokemon-randomizer-zx).
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
    "EVOLUTION_METHOD_NAMES",
    "EVOLUTION_PARAMETER_KINDS",
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
    "parse_evolution_record",
    "parse_item_record",
    "parse_level_up_learnset",
    "parse_move_record",
    "parse_personal_record",
]
