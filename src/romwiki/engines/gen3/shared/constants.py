from __future__ import annotations

# Struct shapes and fixed game-design tables verified byte-identical across
# at least two Generation III families (FireRed/LeafGreen and Emerald) --
# only ROM offsets and per-game record counts differ; those stay in each
# leaf's own constants.py. See each leaf's module comments for the specific
# real-ROM cross-checks that proved a given fact identical.

# `gBaseStats`, 28 bytes, no inline TM/HM bitmap (see `machines.py`).
PERSONAL_RECORD_SIZE = 28

# Real table is 412 entries (dummy + species 1-386 + non-species padding
# 387-411) on both FireRed and Emerald. Bounded to 386, the range PokeDB
# can resolve a slug for.
PERSONAL_RECORD_COUNT = 386

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

# Index 0 is an all-zero placeholder. Move 354 (Psycho Boost) is last real,
# on both FireRed and Emerald.
MOVE_RECORD_SIZE = 12
MOVE_RECORD_COUNT = 355
MAX_MOVE_ID = 354
MOVE_NAME_COUNT = 355

# No damage-class byte in the move struct; derived from power/type instead
# (see `moves.py`).
DAMAGE_CLASS_NAMES = ("status", "physical", "special")

# Index 0 is an all-"?" placeholder. Real item count differs per game
# (FireRed 374, Emerald 376) -- ITEM_RECORD_COUNT stays leaf-specific.
ITEM_RECORD_SIZE = 44

# field_pocket_id 1-5, verified against items spanning every real pocket.
ITEM_POCKET_NAMES = (
    "none",
    "items",
    "key-items",
    "poke-balls",
    "tm-hm",
    "berries",
)

# Species 387-411 are non-species padding; not listed until their slugs
# are confirmed per leaf.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}
PERSONAL_FORM_MEMBERS: dict[int, str] = {}

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

# Index 0 is an all-zero dummy. Real trainer count differs per game
# (FireRed 743, Emerald 855) -- TRAINER_RECORD_COUNT stays leaf-specific.
TRAINER_RECORD_SIZE = 0x28

# `sTMHMLearnsets[][2]`: a separate, species-indexed 64-bit bitmask (two
# u32 halves). Bit N = machine N+1. Verified identical on both games
# (Bulbasaur/Ivysaur share the same 19-machine mask on both).
MACHINE_LEARNSET_SIZE = 8

# `gTMHMMoves[]`: 58 move IDs, TM01-50 then HM01-08, no reordering.
# Verified identical move list/order on both games.
MACHINE_COUNT = 58
TM_COUNT = 50
# TM01 = item 289; TM/HM item IDs are contiguous through HM08 -- a fixed
# item-ID enum shared by every Generation III game's source.
FIRST_MACHINE_ITEM_ID = 289

# `gEvolutionTable[species][5]`: 8-byte slots (method u16, param u16,
# targetSpecies u16, 2 bytes padding). Index 0 is an all-zero dummy;
# bounded to the same 386 species PERSONAL_RECORD_COUNT exposes. Verified
# identical struct shape on both games.
EVOLUTION_SLOT_SIZE = 8
EVOLUTION_SLOT_COUNT = 5
EVOLUTION_RECORD_SIZE = EVOLUTION_SLOT_SIZE * EVOLUTION_SLOT_COUNT

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

# `sTutorMoves[15]`: the base field-tutor move list, verified identical
# (same 15 moves, same order) on both FireRed and Emerald. Emerald layers
# additional Battle Frontier tutors on top of this base set -- a separate,
# leaf-specific extension, not part of this shared fact.
TUTOR_MOVE_COUNT = 15

# `struct MapHeader`, 28 bytes -- verified identical on both games (the
# same `gMapGroups[group][num]` accessor idiom, located via ROM
# disassembly, exists at a unique location in both ROMs).
MAP_HEADER_SIZE = 28
