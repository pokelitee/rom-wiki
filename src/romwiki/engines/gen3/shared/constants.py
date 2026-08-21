from __future__ import annotations

# Struct shapes and fixed game-design tables verified byte-identical across
# at least two Generation III families (FireRed/LeafGreen and Emerald) --
# only ROM offsets and per-game record counts differ; those stay in each
# leaf's own constants.py. See each leaf's module comments for the specific
# real-ROM cross-checks that proved a given fact identical.

# `gBaseStats`, 28 bytes, no inline TM/HM bitmap (see `machines.py`).
PERSONAL_RECORD_SIZE = 28

# Real table is 412 entries (dummy + species 1-411, all real, distinct
# Pokemon -- see INTERNAL_TO_NATIONAL_DEX below) on both FireRed and
# Emerald. Bounded to 386 for now: species 387-411 decode to real personal
# data (verified: internal index 410 decodes to Deoxys's exact real stats,
# 50/150/50/150/150/50), but exposing them needs Unown-letter-form
# deduplication this pass doesn't implement (several of 387-411 map to the
# same National Dex entry, #201 Unown, the same way FORM_MEMBERS already
# handles other forms) -- not yet a guessed real fact, just an unimplemented
# widening.
PERSONAL_RECORD_COUNT = 386

# `sSpeciesToNationalPokedexNum[]` (public pokeemerald/pokefirered
# decompilation `src/pokemon.c`): Generation III's internal `SPECIES_*`
# ordering only matches National Dex order through species 251 (Kanto +
# Johto) -- Hoenn-native species (277 onward) are stored in in-game
# "regional dex discovery order," a completely different sequence, with
# this table converting internal ID -> real National Dex ID for display.
# Verified directly against real ROM data (not just the public source):
# internal index 281 decodes to Combusken's exact real stats (60/85/60/85/
# 60/55) on both the FireRed and Emerald ROMs, while National Dex #281 is
# Kirlia -- confirming the two numbering schemes genuinely diverge before
# the 387-411 range too. Identity entries (internal == national, true for
# every Kanto/Johto species) are omitted; look up with
# `.get(internal_id, internal_id)`.
#
# Internal indices 252-276 (Unown's 25 alternate letter forms, B-Z) are
# deliberately excluded, not identity-mapped: `sSpeciesToNationalPokedexNum`
# itself never assigns them a value in the public source (their would-be
# entries reference `NATIONAL_DEX_OLD_UNOWN_*`, a legacy placeholder block
# the real National Dex enum doesn't include -- confirmed by cross-checking
# `include/constants/pokedex.h`, where `NATIONAL_DEX_COUNT` stops at Deoxys,
# 386, before that block even starts). Unown's real National Dex identity
# is #201 for every letter; resolving these 25 internal indices needs
# `FORM_MEMBERS`-style handling (matching how every other engine's
# alternate forms already work), not a simple id translation -- not yet
# implemented, so `.get(internal_id, internal_id)`'s fallback leaves them
# silently wrong for now rather than crashing, the same class of gap as
# `PERSONAL_RECORD_COUNT` not yet exposing species 387-411.
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

# Species 387-411 are real Pokemon (see INTERNAL_TO_NATIONAL_DEX above),
# not padding -- simply not yet exposed (PERSONAL_RECORD_COUNT is bounded
# to 386). Index 0 is the only genuinely non-species record.
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
