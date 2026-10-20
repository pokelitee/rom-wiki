from __future__ import annotations

# Struct shapes and fixed game-design tables verified byte-identical across
# at least two Generation III families (FireRed/LeafGreen and Emerald) --
# only ROM offsets and per-game record counts differ; those stay in each
# leaf's own constants.py. See each leaf's module comments for the specific
# real-ROM cross-checks that proved a given fact identical.

# `gBaseStats`, 28 bytes, no inline TM/HM bitmap (see `machines.py`).
PERSONAL_RECORD_SIZE = 28

# `gBaseStats` holds a dummy record plus internal species 1-411. 252-276 are
# unused placeholders between Celebi and Treecko (see
# `PERSONAL_INTERNAL_MEMBERS`); every other index is a real Pokémon.
PERSONAL_RECORD_COUNT = 412
LAST_SPECIES_ID = 411

# `sSpeciesToNationalPokedexNum[]` (pokeemerald/pokefirered `src/pokemon.c`):
# internal species numbering matches the National Dex only through Celebi
# (251). Hoenn species (277-411) are stored in Hoenn Dex order, so this
# converts them; e.g. internal 281 is Combusken while National Dex #281 is
# Kirlia. Verified entry-for-entry against the ROM's own table on FireRed
# (0x251FEE) and Emerald (0x31DC82). Identity entries are omitted; look up
# with `.get(internal_id, internal_id)`.
INTERNAL_TO_NATIONAL_DEX: dict[int, int] = {
    277: 252,
    278: 253,
    279: 254,
    280: 255,
    281: 256,
    282: 257,
    283: 258,
    284: 259,
    285: 260,
    286: 261,
    287: 262,
    288: 263,
    289: 264,
    290: 265,
    291: 266,
    292: 267,
    293: 268,
    294: 269,
    295: 270,
    296: 271,
    297: 272,
    298: 273,
    299: 274,
    300: 275,
    301: 290,
    302: 291,
    303: 292,
    304: 276,
    305: 277,
    306: 285,
    307: 286,
    308: 327,
    309: 278,
    310: 279,
    311: 283,
    312: 284,
    313: 320,
    314: 321,
    315: 300,
    316: 301,
    317: 352,
    318: 343,
    319: 344,
    320: 299,
    321: 324,
    322: 302,
    323: 339,
    324: 340,
    325: 370,
    326: 341,
    327: 342,
    328: 349,
    329: 350,
    330: 318,
    331: 319,
    332: 328,
    333: 329,
    334: 330,
    335: 296,
    336: 297,
    337: 309,
    338: 310,
    339: 322,
    340: 323,
    341: 363,
    342: 364,
    343: 365,
    344: 331,
    345: 332,
    346: 361,
    347: 362,
    348: 337,
    349: 338,
    350: 298,
    351: 325,
    352: 326,
    353: 311,
    354: 312,
    355: 303,
    356: 307,
    357: 308,
    358: 333,
    359: 334,
    361: 355,
    362: 356,
    363: 315,
    364: 287,
    365: 288,
    366: 289,
    367: 316,
    368: 317,
    369: 357,
    370: 293,
    371: 294,
    372: 295,
    373: 366,
    374: 367,
    375: 368,
    376: 359,
    377: 353,
    378: 354,
    379: 336,
    380: 335,
    381: 369,
    382: 304,
    383: 305,
    384: 306,
    385: 351,
    386: 313,
    387: 314,
    388: 345,
    389: 346,
    390: 347,
    391: 348,
    392: 280,
    393: 281,
    394: 282,
    395: 371,
    396: 372,
    397: 373,
    398: 374,
    399: 375,
    400: 376,
    401: 377,
    402: 378,
    403: 379,
    404: 382,
    405: 383,
    406: 384,
    407: 380,
    408: 381,
    409: 385,
    410: 386,
    411: 358,
}

# `gAbilityNames` matches PokéDB's numbering through Shell Armor (75). Index
# 76 is Cacophony, which no Pokémon has and PokéDB omits, and Air Lock
# follows at 77, which PokéDB numbers 76. Verified on FireRed and Emerald.
ABILITY_REFERENCE_IDS: dict[int, int | None] = {76: None, 77: 76}

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

# Index 0 and the 25 placeholder species 252-276 (`SPECIES_OLD_UNOWN_B`-`_Z`
# in the decompilations). The ROM names each "?" and gives it the same
# dummy stats (50/150/50/150/150/50, no abilities); they are never
# obtainable, and the Dex table maps them past National Dex #386.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {
    0: "none",
    **{
        252 + offset: f"old-unown-{letter}"
        for offset, letter in enumerate("bcdefghijklmnopqrstuvwxyz")
    },
}
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

# `gTrainerClassNames`: 13-byte names indexed by a trainer's class ID, just
# before the trainer table on both games. The class count differs per game.
TRAINER_CLASS_NAME_SIZE = 13

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
# targetSpecies u16, 2 bytes padding), one per personal record. Index 0 is
# an all-zero dummy. Verified identical struct shape on both games.
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

# `struct MapHeader`, 28 bytes -- verified identical on both games (the
# same `gMapGroups[group][num]` accessor idiom, located via ROM
# disassembly, exists at a unique location in both ROMs).
MAP_HEADER_SIZE = 28

# The leading 24 bytes of `struct MapLayout` -- width and height (s32 each),
# then border, map, primary-tileset, and secondary-tileset pointers -- shared
# by both games. They're read only to tell a real map header from other data.
MAP_LAYOUT_PREFIX_SIZE = 24
# Generous sanity bound for a layout's width and height.
MAX_MAP_DIMENSION = 0x400
# Map groups and map numbers are each a u8.
MAX_MAP_GROUPS = 256
MAX_MAPS_PER_GROUP = 256

# `WildPokemonHeader`, 20 bytes -- one entry per map (mapGroup/mapNum, not a
# species-style index), so no dummy record. Verified identical struct shape
# on both games (FireRed's table decodes real Kanto data; Emerald's table,
# at its own offset, decodes real Hoenn data -- e.g. Emerald header 0
# (mapGroup 0/mapNum 16) decodes to Wurmple/Poochyena/Zigzagoon, Route 101's
# real land encounters, and header 1 (mapNum 17) includes Ralts, Route 102's
# well-known Emerald-exclusive encounter). Per-game table offset/count stay
# leaf-specific (FireRed/LeafGreen 132 entries, Emerald 124), each
# terminated by a {0xFF, 0xFF, ...} sentinel.
ENCOUNTER_HEADER_SIZE = 20

# Rock Smash shares water's slot count per the public decompilation's
# `WILD_TABLE_ROWS`. Verified identical on both games (Emerald's rock-smash
# table, e.g. mapGroup 0/mapNum 26, decodes to exactly 5 Geodude slots
# before running into the next struct's bytes).
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

# Explicit "nothing stored" declarations for adapter members other engines
# populate: no battle-transformation personal records, no form-specific wild
# encounters, and duplicate egg moves are malformed rather than tolerated.
TRANSFORMATION_MEMBERS: dict[int, dict[str, str]] = {}
ENCOUNTER_FORM_SLUGS: dict[tuple[int, int], str] = {}
ENCOUNTER_COSMETIC_FORM_LABELS: dict[tuple[int, int], str] = {}
ALLOW_DUPLICATE_EGG_MOVES = False

# A Pokémon's nature is its personality value modulo 25, in this order.
NATURE_NAMES = (
    "Hardy",
    "Lonely",
    "Brave",
    "Adamant",
    "Naughty",
    "Bold",
    "Docile",
    "Relaxed",
    "Impish",
    "Lax",
    "Timid",
    "Hasty",
    "Serious",
    "Jolly",
    "Naive",
    "Modest",
    "Mild",
    "Quiet",
    "Bashful",
    "Rash",
    "Calm",
    "Gentle",
    "Sassy",
    "Careful",
    "Quirky",
)

# `gPokedexEntries` covers National Dex 0 (unknown) through 386.
POKEDEX_ENTRY_COUNT = 387
POKEDEX_DESCRIPTION_POINTER = 0x10
