# Personal (species) stats archive `a/0/1/6`: national dex species occupy
# members 1-649, member 0 is an unused placeholder record, and members
# 650-667 are 18 alternate-forme records (Therian formes, Kyurem-B/W,
# seasonal Deerling/Sawsbuck, Genesect drives, Keldeo, Meloetta, etc.).
# Confirmed empirically against a real Black ROM: `a/0/1/6` has 669 total
# archive members; the last (index 668) is a 1300-byte table unrelated to
# personal records and is excluded from PERSONAL_RECORD_COUNT.
GEN5_BASE_SPECIES_COUNT = 649
PERSONAL_RECORD_COUNT = 668

# PersonalInfo5BW.SIZE (PKHeX.Core/PersonalInfo/Info/PersonalInfo5BW.cs);
# confirmed against a real Black ROM record (Bulbasaur, member 1).
PERSONAL_RECORD_SIZE = 0x3C

# Unlike every other member (all a uniform PERSONAL_RECORD_SIZE), the member 0
# "none" placeholder is a distinct, shorter 56-byte record in a real Black
# ROM. Its content is unused (species 0 is never a real Pokémon), so
# `parse_personal_record` zero-pads it rather than rejecting it.
PERSONAL_PLACEHOLDER_MEMBER = 0
PERSONAL_PLACEHOLDER_RECORD_SIZE = 56

# Forme records (650-667) are not yet resolved to named public pages -- see
# docs/development/adding-a-game.md's incremental-slice guidance. They parse
# as ordinary personal records but are kept non-public via a placeholder slug
# until a future slice maps each index to its real species/form.
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {
    0: "none",
    **{member: f"form-{member}" for member in range(650, 668)},
}
PERSONAL_FORM_MEMBERS: dict[int, str] = {}

# TM01-95, HM01-06 (Gen5Constants.tmCount / hmCount, Ajarmar/universal-pokemon-randomizer-zx).
GEN5_TM_COUNT = 95
GEN5_HM_COUNT = 6
GEN5_MACHINE_COUNT = GEN5_TM_COUNT + GEN5_HM_COUNT

# Byte-order type table (Gen5Constants.constructTypeTable(), Ajarmar/universal-
# pokemon-randomizer-zx); confirmed against a real Black ROM record (Bulbasaur
# decodes to grass=11/poison=3 at this table's indices). No Fairy type yet and,
# unlike Gen4, no reserved "unknown" placeholder slot.
TYPE_NAME_COUNT = 17
TYPE_NAMES = (
    "normal", "fighting", "flying", "poison", "ground", "rock", "bug",
    "ghost", "steel", "fire", "water", "grass", "electric", "psychic",
    "ice", "dragon", "dark",
)

# Unchanged from earlier generations' identical engine-internal ID schemes;
# confirmed against a real Black ROM record (Bulbasaur: egg groups
# monster/grass, growth rate medium-slow, color green all decode correctly
# against these tables).
EGG_GROUP_NAMES = (
    "none", "monster", "water-1", "bug", "flying", "field", "fairy",
    "grass", "human-like", "water-3", "mineral", "amorphous", "water-2",
    "ditto", "dragon", "undiscovered",
)
GROWTH_RATE_NAMES = (
    "medium-fast", "erratic", "fluctuating", "medium-slow", "fast", "slow",
)
COLOR_NAMES = (
    "red", "blue", "yellow", "green", "black", "brown", "purple", "gray",
    "white", "pink", "internal",
)

# Name-table entry counts, confirmed empirically by decoding every entry in
# a real Black ROM's `a/0/0/2` (TextStrings) NARC -- see messages.py. Each
# includes a leading placeholder entry (index 0) and, for Pokémon, two
# trailing "Egg" entries (650-651) alongside the 649 real species.
MOVE_NAME_COUNT = 560
ABILITY_NAME_COUNT = 165
ITEM_NAME_COUNT = 627
POKEMON_NAME_COUNT = 652

# MOVE_RECORD_COUNT/MAX_MOVE_ID describe the (still unimplemented) move *data*
# archive, a different table from the move *names* text above -- not yet
# verified against ROM data; no profile configures a moves layout entry yet,
# so these counts are unreached by pipeline/enrich.py's validation paths.
MOVE_RECORD_COUNT = 559
MAX_MOVE_ID = 559
