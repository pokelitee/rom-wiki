from __future__ import annotations

# Generation III's personal-info struct (`gBaseStats` in the public
# pokefirered/pokeemerald decompilations) is a fixed 28-byte record with no
# inline TM/HM compatibility bitmap -- that lives in a separate
# `gTMHMLearnsets` table, out of scope until the machines concern is added.
PERSONAL_RECORD_SIZE = 28

# FireRed/LeafGreen's personal-info table actually holds 412 entries
# (verified against the real ROM -- see personal_offset in the profile
# TOML): a dummy record at index 0, National Dex species 1-386, then
# non-species padding (Egg/Unown-letter/Deoxys-forme slots per the public
# pokefirered decompilation) through index 411. Bounded here to 386 -- the
# National Dex range PokeDB can actually resolve a slug/reference for --
# until the padding range's per-index slugs are confirmed and added to
# PERSONAL_INTERNAL_MEMBERS/PERSONAL_FORM_MEMBERS below.
PERSONAL_RECORD_COUNT = 386

# Generation III kept the reserved "???" (Mystery) type slot at index 9
# that Generation IV also still had (removed only when Fairy was added in
# Generation VI) -- identical ordering to `engines/gen4/constants.py`'s own
# table, kept as a separate literal here rather than imported across engine
# leaves per this repo's package-boundary rule.
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

# Unchanged from Generation IV/V's identical engine-internal ID scheme.
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

# `pipeline/enrichment/names.py`'s resolve_*_names helpers read these
# unconditionally (before checking whether the raw dataset actually carries
# the corresponding ROM-derived name table), even though reference-name
# extraction isn't implemented for gen3_frlg yet -- the personal-data
# vertical slice never populates `move_names`/`ability_names`/`item_names`/
# `pokemon_names` in its dataset, so these counts are never actually
# validated against anything. Zero rather than a guessed real count, so
# nothing here looks like a verified fact it isn't.
MOVE_NAME_COUNT = 0
ABILITY_NAME_COUNT = 0
ITEM_NAME_COUNT = 0
POKEMON_NAME_COUNT = 0
POKEMON_DESCRIPTION_COUNT = 0

# Verified against the real ROM (see personal.py): species 0 is an all-zero
# placeholder record, not a real Pokemon -- matches the same {0: "none"}
# convention `engines/gen5/bw/constants.py`'s PERSONAL_INTERNAL_MEMBERS uses.
# FRLG's personal table also has non-species padding near the end (species
# 387-411, likely Egg/Unown-letter/Deoxys-forme slots per the public
# pokefirered decompilation), but which slug maps to which index hasn't been
# verified against a real ROM yet, so none are listed here rather than
# guessing -- add them once confirmed, following this same pattern.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}
PERSONAL_FORM_MEMBERS: dict[int, str] = {}

# Unchanged body-color ID scheme across Generation III-V (verified: Bulbasaur
# decodes to body_color_id=3 here, matching this table's "green" -- Bulbasaur
# is documented as Green in every generation's Pokedex color field). Kept as
# a separate literal rather than imported across engine leaves per this
# repo's package-boundary rule -- see `engines/gen5/bw/constants.py`'s
# identical table.
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
