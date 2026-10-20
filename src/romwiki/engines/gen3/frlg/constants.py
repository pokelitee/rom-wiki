from __future__ import annotations

# Re-exported for `pipeline/extraction/*.py`'s `engine.<NAME>` flat-namespace
# convention -- struct shapes and fixed game-design tables proven identical
# across at least two Generation III families (FireRed/LeafGreen and
# Emerald) live in `gen3/shared/constants.py`; only ROM offsets and
# per-game record counts stay here.
from romwiki.engines.gen3.shared.constants import (
    COLOR_NAMES as COLOR_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    DAMAGE_CLASS_NAMES as DAMAGE_CLASS_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    EGG_GROUP_NAMES as EGG_GROUP_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    EVOLUTION_METHOD_NAMES as EVOLUTION_METHOD_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    EVOLUTION_PARAMETER_KINDS as EVOLUTION_PARAMETER_KINDS,
)
from romwiki.engines.gen3.shared.constants import (
    EVOLUTION_RECORD_SIZE as EVOLUTION_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    EVOLUTION_SLOT_COUNT as EVOLUTION_SLOT_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    EVOLUTION_SLOT_SIZE as EVOLUTION_SLOT_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    FIRST_MACHINE_ITEM_ID as FIRST_MACHINE_ITEM_ID,
)
from romwiki.engines.gen3.shared.constants import (
    GROWTH_RATE_NAMES as GROWTH_RATE_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    INTERNAL_TO_NATIONAL_DEX as INTERNAL_TO_NATIONAL_DEX,
)
from romwiki.engines.gen3.shared.constants import (
    ITEM_POCKET_NAMES as ITEM_POCKET_NAMES,
)
from romwiki.engines.gen3.shared.constants import (
    ITEM_RECORD_SIZE as ITEM_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    MACHINE_COUNT as MACHINE_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    MACHINE_LEARNSET_SIZE as MACHINE_LEARNSET_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    MAP_HEADER_SIZE as MAP_HEADER_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    MAX_MOVE_ID as MAX_MOVE_ID,
)
from romwiki.engines.gen3.shared.constants import (
    MOVE_NAME_COUNT as MOVE_NAME_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    MOVE_RECORD_COUNT as MOVE_RECORD_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    MOVE_RECORD_SIZE as MOVE_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    PERSONAL_FORM_MEMBERS as PERSONAL_FORM_MEMBERS,
)
from romwiki.engines.gen3.shared.constants import (
    PERSONAL_INTERNAL_MEMBERS as PERSONAL_INTERNAL_MEMBERS,
)
from romwiki.engines.gen3.shared.constants import (
    PERSONAL_RECORD_COUNT as PERSONAL_RECORD_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    PERSONAL_RECORD_SIZE as PERSONAL_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    TM_COUNT as TM_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    TRAINER_RECORD_SIZE as TRAINER_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.constants import (
    TYPE_NAME_COUNT as TYPE_NAME_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    TYPE_NAMES as TYPE_NAMES,
)

# `gSpeciesNames`: one 11-byte name per personal record. Pokédex entries
# come from PokéDB rather than the ROM, so there is no description table.
ITEM_NAME_COUNT = 375
POKEMON_NAME_COUNT = 412
POKEMON_DESCRIPTION_COUNT = 0

# `gAbilityNames` runs through index 77 ("AIR LOCK"); see
# `ABILITY_REFERENCE_IDS` for how it maps onto PokéDB's numbering.
ABILITY_NAME_COUNT = 78

# FireRed/LeafGreen's real item count (Sapphire, item 374, is last real).
# Differs per game (Emerald has 376) -- not a shared fact.
ITEM_RECORD_COUNT = 375

# FireRed/LeafGreen's real trainer count (index 742, "PAXTON", is last
# real). Differs per game (Emerald has 854) -- not a shared fact.
TRAINER_RECORD_COUNT = 743

# Classes 0 ("PKMN TRAINER") through 106 ("PAINTER"); trainers use 0-106.
TRAINER_CLASS_COUNT = 107

# `gTutorMoves`: 15 tutor moves, each with a bit in a species' 2-byte
# `sTutorLearnsets` mask.
TUTOR_MOVE_COUNT = 15
TUTOR_COMPATIBILITY_SIZE = 2

# Generation III has no per-tutor location table -- only individual NPC
# scripts. Each tutor script's `setvar VAR_0x8005, <index>; call
# EventScript_ChooseMoveTutorMon` is a unique signature occurring exactly 15
# times in the ROM. Matching those scripts against every map's overworld
# objects placed all 15 on both games: nine NPCs' scripts start 54 bytes
# before the signature, five start with a `goto` into it, and Mimic's
# Saffron City NPC reaches it from a longer script that checks for a Poké
# Doll first.
#
# Maps each `sTutorMoves` index to its Town Map region name rather than a
# synthetic `header_id`; the extraction layer resolves the name to the
# first of that profile's maps with it.
TUTOR_LOCATIONS = {
    0: "Route 4",  # Mega Punch
    1: "Seven Island",  # Swords Dance
    2: "Route 4",  # Mega Kick
    3: "Four Island",  # Body Slam
    4: "Victory Road",  # Double-Edge
    5: "Celadon City",  # Counter
    6: "Pewter City",  # Seismic Toss
    7: "Saffron City",  # Mimic
    8: "Cinnabar Island",  # Metronome
    9: "Celadon City",  # Softboiled
    10: "Viridian City",  # Dream Eater
    11: "Silph Co.",  # Thunder Wave
    12: "Mt. Ember",  # Explosion
    13: "Rock Tunnel",  # Rock Slide
    14: "Fuchsia City",  # Substitute
}

# One entry per map (mapGroup/mapNum, not a species-style index), so no
# dummy record. Terminated by a {0xFF, 0xFF, ...} sentinel. Struct shape
# and slot counts are shared (see `gen3/shared/constants.py`'s
# `ENCOUNTER_HEADER_SIZE`); only this count differs per game (Emerald has
# 124).
ENCOUNTER_HEADER_COUNT = 132


# `sMapNames`: one name pointer per Kanto/Sevii region map section. FireRed/
# LeafGreen's sections start at 88 (`KANTO_MAPSEC_START`), after the Hoenn
# sections they share numbering with, so section 88 (Pallet Town) is entry
# 0. Verified against the maps' own sections: group 3's map 0 is section 88
# and map 19 (Route 1) is section 101.
REGION_NAME_ENTRY_SIZE = 4
REGION_NAME_POINTER_OFFSET = 0
FIRST_REGION_MAP_SECTION = 88

# Trainer IDs per rematch-table row, and the mechanic that offers rematches.
REMATCH_TRAINERS_PER_ENTRY = 6
REMATCH_LABEL = "Vs. Seeker"

# `struct PokedexEntry`: 36 bytes (FireRed/LeafGreen also keep an unused second description pointer); the description pointer
# sits at 0x10.
POKEDEX_ENTRY_SIZE = 0x24

# `VAR_STARTER_MON`, the chosen starter's index (pret `include/constants/vars.h`).
STARTER_VAR = 0x4031
