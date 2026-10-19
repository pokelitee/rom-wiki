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
    TUTOR_MOVE_COUNT as TUTOR_MOVE_COUNT,
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
# dummy record. Terminated by a {0xFF, 0xFF, ...} sentinel. Struct shape
# and slot counts are shared (see `gen3/shared/constants.py`'s
# `ENCOUNTER_HEADER_SIZE`); only this count differs per game (Emerald has
# 124).
ENCOUNTER_HEADER_COUNT = 132

# `gMapGroups`'s own base: an array of pointers, one per map group, each to
# that group's own array of pointers-to-`MapHeader`. Located via ROM
# disassembly (the `gMapGroups[group][num]` accessor's literal pool value
# at file offset 0x05524C). Exactly 43 groups on both FireRed and
# LeafGreen (Emerald's own count differs -- 34 -- so this stays leaf-
# specific). Used only to backfill wild-encounter `locations` within the
# already-decoded Sevii Islands/postgame span -- Kanto maps aren't covered
# (see `locations.py`).
GMAPGROUPS_GROUP_COUNT = 43
