from __future__ import annotations

# `gBaseStats`, 28 bytes, no inline TM/HM bitmap (see `machines.py`).
PERSONAL_RECORD_SIZE = 28

# Real table is 412 entries (dummy + species 1-386 + non-species padding
# 387-411). Bounded to 386, the range PokeDB can resolve a slug for.
PERSONAL_RECORD_COUNT = 386

# Same "???" Mystery slot at index 9 as Generation IV. Not imported from
# `gen4/constants.py` (package-boundary rule).
TYPE_NAME_COUNT = 18
TYPE_NAMES = (
    "normal",
    "fighting",
    "flying",
    "poison",
    "ground",
    "rock",
    "bug",
    "ghost",
    "steel",
    "unknown",
    "fire",
    "water",
    "grass",
    "electric",
    "psychic",
    "ice",
    "dragon",
    "dark",
)

EGG_GROUP_NAMES = (
    "none",
    "monster",
    "water-1",
    "bug",
    "flying",
    "field",
    "fairy",
    "grass",
    "human-like",
    "water-3",
    "mineral",
    "amorphous",
    "water-2",
    "ditto",
    "dragon",
    "undiscovered",
)
GROWTH_RATE_NAMES = (
    "medium-fast",
    "erratic",
    "fluctuating",
    "medium-slow",
    "fast",
    "slow",
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

# Index 0 is an all-zero placeholder. Move 354 (Psycho Boost) is last real.
MOVE_RECORD_SIZE = 12
MOVE_RECORD_COUNT = 355
MAX_MOVE_ID = 354

MOVE_NAME_COUNT = 355

# No damage-class byte in the move struct; derived from power/type instead
# (see moves.py). Same ordering as `gen5/bw/constants.py`.
DAMAGE_CLASS_NAMES = ("status", "physical", "special")

# Index 0 is an all-"?" placeholder. Item 374 (Sapphire) is last real.
ITEM_RECORD_SIZE = 44
ITEM_RECORD_COUNT = 375

# field_pocket_id 1-5, verified against items spanning every real pocket.
ITEM_POCKET_NAMES = (
    "none",
    "items",
    "key-items",
    "poke-balls",
    "tm-hm",
    "berries",
)

# Species 387-411 are non-species padding (Egg/Unown/Deoxys-forme slots per
# the public decompilation); not listed until their slugs are confirmed.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}
PERSONAL_FORM_MEMBERS: dict[int, str] = {}

# Same body-color scheme as Generation IV/V. Not imported across engine
# leaves (package-boundary rule) -- see `gen5/bw/constants.py`.
COLOR_NAMES = (
    "red",
    "blue",
    "yellow",
    "green",
    "black",
    "brown",
    "purple",
    "gray",
    "white",
    "pink",
    "internal",
)

# Index 0 is an all-zero dummy. Trainer 742 ("PAXTON") is last real.
TRAINER_RECORD_SIZE = 0x28
TRAINER_RECORD_COUNT = 743

# `sTMHMLearnsets[][2]`: a separate, species-indexed 64-bit bitmask (two
# u32 halves), unlike Gen IV/V's inline bitmap. Bit N = machine N+1.
MACHINE_LEARNSET_SIZE = 8

# `gTMHMMoves[]`: 58 move IDs, TM01-50 then HM01-08, no reordering.
MACHINE_COUNT = 58
TM_COUNT = 50
# TM01 = item 289; TM/HM item IDs are contiguous through HM08.
FIRST_MACHINE_ITEM_ID = 289

# `gEvolutionTable[species][5]`: 8-byte slots (method u16, param u16,
# targetSpecies u16, 2 bytes padding). Index 0 is an all-zero dummy;
# bounded to the same 386 species PERSONAL_RECORD_COUNT exposes.
EVOLUTION_SLOT_SIZE = 8
EVOLUTION_SLOT_COUNT = 5
EVOLUTION_RECORD_SIZE = EVOLUTION_SLOT_SIZE * EVOLUTION_SLOT_COUNT

# `sTutorMoves[15]`/`sTutorLearnsets[]`: flat move-ID array plus a
# per-species u16 compatibility bitmask (bit N = tutor index N).
TUTOR_MOVE_COUNT = 15

# Generation III has no per-tutor location table -- only individual NPC
# scripts. Verified via ROM disassembly (each tutor script's `setvar
# VAR_0x8005, <index>; call EventScript_ChooseMoveTutorMon` is a unique
# signature occurring exactly 15 times in the ROM); cross-referencing those
# 15 script addresses against every overworld object on the already-decoded
# Sevii Islands/postgame segments found exactly 4 real matches (identical
# on both games). The other 11 tutors are in Kanto, which this engine has
# no map-header data for (see `locations.py`) -- excluded rather than
# guessed. Maps each `sTutorMoves` index to its location `header_id`.
TUTOR_LOCATIONS = {
    0: 15,  # Mega Punch -> Scufib Chamber
    2: 15,  # Mega Kick -> Scufib Chamber
    5: 30,  # Counter -> Rocket Warehouse
    14: 7,  # Substitute -> Altering Cave
}

# Matches Generation IV's evolution-method numbering through "beauty"
# (index 15); Generation III's `EVO_*` enum has nothing beyond it.
EVOLUTION_METHOD_NAMES = (
    "none",
    "friendship",
    "friendship-day",
    "friendship-night",
    "level",
    "trade",
    "trade-held-item",
    "use-item",
    "level-attack-greater",
    "level-attack-equal",
    "level-defense-greater",
    "level-personality-low",
    "level-personality-high",
    "level-ninjask",
    "level-shedinja",
    "beauty",
)
EVOLUTION_PARAMETER_KINDS = {
    **dict.fromkeys((4, 8, 9, 10), "level"),
    **dict.fromkeys((6, 7), "item"),
    11: "personality",
    12: "personality",
    15: "beauty",
}

# One entry per map (mapGroup/mapNum, not a species-style index), so no
# dummy record. Terminated by a {0xFF, 0xFF, ...} sentinel.
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

# `struct MapHeader`, 28 bytes.
MAP_HEADER_SIZE = 28

# Town Map region-name table: variable-length, back-to-back,
# 0xFF-terminated (see `text.py`'s `decode_gen3_text_sequence`), not
# fixed-stride like every other name table. Exactly 109 entries on both
# games (index 0 = "PALLET TOWN" ... 108 = "CELADON DEPT.").
MAP_HEADER_REGION_COUNT = 109

# `gMapGroups`'s own base: an array of pointers, one per map group, each to
# that group's own array of pointers-to-`MapHeader`. Located via ROM
# disassembly (the `gMapGroups[group][num]` accessor's literal pool value
# at file offset 0x05524C). Exactly 43 groups on both games. Used only to
# backfill wild-encounter `locations` within the already-decoded Sevii
# Islands/postgame span -- Kanto maps aren't covered (see `locations.py`).
GMAPGROUPS_GROUP_COUNT = 43
