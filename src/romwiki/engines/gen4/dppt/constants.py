PLATINUM_DYNAMIC_WARP_HEADER_ID = 0x0FFF
PLATINUM_DYNAMIC_WARP_ID = 0x0100
PLATINUM_MATRIX_VOID_HEADER_IDS = frozenset((0, 0xFFFF))

# Map headers with a honey tree, in HoneyTree_TryInteract's fixed sHoneyTreeMapHeaderIDs
# order (src/overlay005/honey_tree.c). Which specific tree is the player's guaranteed
# Munchlax tree is derived from the save file's trainer ID, not ROM data.
PLATINUM_HONEY_TREE_HEADER_IDS = (
    347,
    349,
    350,
    353,
    354,
    356,
    362,
    363,
    366,
    367,
    371,
    373,
    380,
    382,
    388,
    392,
    395,
    200,
    202,
    204,
    256,
)
# Great Marsh areas 1-6 (src/overlay006/great_marsh_daily_encounters.c); all six
# areas share the same daily species pool.
PLATINUM_GREAT_MARSH_HEADER_IDS = (504, 505, 506, 507, 508, 509)
PLATINUM_TROPHY_GARDEN_HEADER_ID = 287

# Species for each ROAMING_SLOT_* index (src/roaming_pokemon.c's
# RoamingPokemon_ActivateSlot switch), in generated/roaming_slots.txt order:
# Mesprit, Cresselia, Darkrai, Moltres, Zapdos. Only 5 entries — matches
# PLATINUM_ROAMING_SLOT_COUNT (scripts.py); no observed or retail-reachable
# script ever activates the 6th slot (Articuno). This mapping is a compiled
# ARM9 constant, not ROM table data; verified against real script calls
# (Verity Cavern activates slot 0, Fullmoon Island slot 1, Eterna City slots
# 3/4). Level is also a compiled constant but was not verified per-ROM and is
# intentionally not exposed here — see README.
PLATINUM_ROAMING_SLOT_SPECIES_IDS = (481, 488, 491, 146, 145)

# Veilstone City's Prize Exchange counter (src/scrcmd_game_corner_prize.c
# reads a 19-entry {item, price} table at a fixed ARM9 offset, configured per
# profile as game_corner_prize_table_offset/game_corner_prize_count since it's
# a raw code address, not ROM archive data).
PLATINUM_GAME_CORNER_PRIZE_EXCHANGE_HEADER_ID = 144
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

# Engine ID-to-name tables live in the shared Generation IV package. Retail
# D/P/Pt and HGSS ROM fixtures prove the personal-record shape and these IDs.
DAMAGE_CLASS_NAMES = ("physical", "special", "status")
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
    "use-item-male",
    "use-item-female",
    "level-held-item-day",
    "level-held-item-night",
    "level-knowing-move",
    "level-with-party-species",
    "level-male",
    "level-female",
    "level-magnetic-field",
    "level-moss-rock",
    "level-ice-rock",
)
# How each evolution method's parameter operand should be interpreted.
# Methods absent here either take no parameter or an unknown raw value.
EVOLUTION_PARAMETER_KINDS = {
    **dict.fromkeys((4, 8, 9, 10, 13, 14, 22, 23), "level"),
    **dict.fromkeys((6, 7, 16, 17, 18, 19), "item"),
    11: "personality",
    12: "personality",
    15: "beauty",
    20: "move",
    21: "pokemon",
}
