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
    TUTOR_MOVE_COUNT as TUTOR_MOVE_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    TYPE_NAME_COUNT as TYPE_NAME_COUNT,
)
from romwiki.engines.gen3.shared.constants import (
    TYPE_NAMES as TYPE_NAMES,
)

# Zero rather than a guessed count for domains not yet implemented; real
# once the corresponding table lands (moves/items/abilities are; pokemon
# name/description tables aren't yet).
ITEM_NAME_COUNT = 375
POKEMON_NAME_COUNT = 0
POKEMON_DESCRIPTION_COUNT = 0

# Real table runs to index 77 ("AIR LOCK"), but index 76 ("CACOPHONY") has
# no PokeDB counterpart -- a one-entry numbering divergence. No decoded
# species (1-386) references ability 76 or 77, so bounding at 76 loses
# nothing currently exposed; revisit once species 387-411 are exposed
# (species 406 references Air Lock).
ABILITY_NAME_COUNT = 76

# FireRed/LeafGreen's real item count (Sapphire, item 374, is last real).
# Differs per game (Emerald has 376) -- not a shared fact.
ITEM_RECORD_COUNT = 375

# FireRed/LeafGreen's real trainer count (index 742, "PAXTON", is last
# real). Differs per game (Emerald has 854) -- not a shared fact.
TRAINER_RECORD_COUNT = 743

# Generation III has no per-tutor location table -- only individual NPC
# scripts. Verified via ROM disassembly (each tutor script's `setvar
# VAR_0x8005, <index>; call EventScript_ChooseMoveTutorMon` is a unique
# signature occurring exactly 15 times in the ROM); cross-referencing those
# 15 script addresses against every overworld object on the already-decoded
# Sevii Islands/postgame segments found exactly 4 real matches (identical
# on both games). The other 11 tutors are in Kanto, which this engine has
# no map-header data for (see `locations.py`) -- excluded rather than
# guessed.
#
# Maps each `sTutorMoves` index to its Town Map region name -- not a
# `header_id`. `header_id` is a synthetic number the extraction layer
# assigns from `map_header_segments`' list order, so it isn't guaranteed
# stable across profiles (FireRed and LeafGreen only agree because both
# happen to list their 3 segments in the same order). Region name is a
# real ROM-native fact (`regionMapSectionId` on the `MapHeader` struct
# itself), so the extraction layer resolves it to that profile's own
# `header_id` at read time instead of trusting a baked-in number.
TUTOR_LOCATIONS = {
    0: "SCUFIB CHAMBER",  # Mega Punch
    2: "SCUFIB CHAMBER",  # Mega Kick
    5: "ROCKET WAREHOUSE",  # Counter
    14: "ALTERING CAVE",  # Substitute
}

# One entry per map (mapGroup/mapNum, not a species-style index), so no
# dummy record. Terminated by a {0xFF, 0xFF, ...} sentinel. Not yet
# verified against Emerald's own encounter tables -- FireRed/LeafGreen-
# specific until that's checked.
ENCOUNTER_HEADER_SIZE = 20
ENCOUNTER_HEADER_COUNT = 132

# Rock Smash shares water's slot count per the public decompilation's
# `WILD_TABLE_ROWS`.
ENCOUNTER_LAND_SLOT_COUNT = 12
ENCOUNTER_WATER_SLOT_COUNT = 5
ENCOUNTER_ROCK_SMASH_SLOT_COUNT = 5
ENCOUNTER_FISHING_SLOT_COUNT = 10

ENCOUNTER_METHOD_NAMES = ("land", "water", "rock_smash", "fishing")

# Fixed game-design percentages (not ROM-derived), unchanged since
# Generation III. Fishing concatenates all three rods into one 10-slot
# table (unlike Gen IV+, which splits each rod into its own method).
ENCOUNTER_LAND_SLOT_CHANCES = (20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1)
ENCOUNTER_WATER_SLOT_CHANCES = (60, 30, 5, 4, 1)
ENCOUNTER_ROCK_SMASH_SLOT_CHANCES = (60, 30, 5, 4, 1)
ENCOUNTER_FISHING_SLOT_CHANCES = (70, 30, 60, 20, 20, 40, 40, 15, 4, 1)

# Town Map region-name table: variable-length, back-to-back,
# 0xFF-terminated (see `shared/text.py`'s `decode_gen3_text_sequence`), not
# fixed-stride like every other name table. Exactly 109 entries on both
# FireRed and LeafGreen (index 0 = "PALLET TOWN" ... 108 = "CELADON
# DEPT."). Emerald's own region-name table is a real superset (197
# entries, including Kanto and all of Sevii Islands) -- not the same
# count, so this stays leaf-specific.
MAP_HEADER_REGION_COUNT = 109

# `gMapGroups`'s own base: an array of pointers, one per map group, each to
# that group's own array of pointers-to-`MapHeader`. Located via ROM
# disassembly (the `gMapGroups[group][num]` accessor's literal pool value
# at file offset 0x05524C). Exactly 43 groups on both FireRed and
# LeafGreen (Emerald's own count differs -- 34 -- so this stays leaf-
# specific). Used only to backfill wild-encounter `locations` within the
# already-decoded Sevii Islands/postgame span -- Kanto maps aren't covered
# (see `locations.py`).
GMAPGROUPS_GROUP_COUNT = 43
