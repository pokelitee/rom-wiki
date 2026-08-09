GEN4_ARCHIVE_MEMBER_NONE = 0xFFFF
GEN4_MAX_FRIENDSHIP = 255

PERSONAL_RECORD_COUNT = 508
MOVE_RECORD_COUNT = 471
MAX_MOVE_ID = 467
TYPE_NAME_COUNT = 18
ABILITY_NAME_COUNT = 124
ITEM_NAME_COUNT = 468
MOVE_NAME_COUNT = 468
POKEMON_NAME_COUNT = 496
NATURAL_GIFT_TYPE_NONE = 31
DAMAGE_CLASS_NAMES = ("physical", "special", "status")

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

NATURE_NAMES = (
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
)

EVOLUTION_METHOD_NAMES = (
    "none", "friendship", "friendship-day", "friendship-night", "level",
    "trade", "trade-held-item", "use-item", "level-attack-greater",
    "level-attack-equal", "level-defense-greater", "level-personality-low",
    "level-personality-high", "level-ninjask", "level-shedinja", "beauty",
    "use-item-male", "use-item-female", "level-held-item-day",
    "level-held-item-night", "level-knowing-move", "level-with-party-species",
    "level-male", "level-female", "level-magnetic-field", "level-moss-rock",
    "level-ice-rock",
)

EVOLUTION_PARAMETER_KINDS = {
    **dict.fromkeys((4, 8, 9, 10, 13, 14, 22, 23), "level"),
    **dict.fromkeys((6, 7, 16, 17, 18, 19), "item"),
    11: "personality",
    12: "personality",
    15: "beauty",
    20: "move",
    21: "pokemon",
}
