# Personal (species) stats archive `a/0/1/6`: national dex species occupy
# members 1-649, member 0 is an unused placeholder record, and members
# 650-667 are 18 alternate-forme/battle-transformation records (Deoxys,
# Wormadam, Giratina, Shaymin, Rotom, Basculin, Castform, Darmanitan,
# Meloetta -- see PERSONAL_FORM_MEMBERS/PERSONAL_TRANSFORMATION_MEMBERS
# below for the exact, verified mapping). Confirmed empirically against a
# real Black ROM: `a/0/1/6` has 669 total archive members; the last (index
# 668) is a 1300-byte table unrelated to personal records and is excluded
# from PERSONAL_RECORD_COUNT.
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

PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}

# The 18 forme records (650-667) identified by decoding their real base
# stats/types from a Black ROM and cross-referencing against
# Ajarmar/universal-pokemon-randomizer-zx's Gen5Constants.java, which has an
# authoritative `bw1FormeCount = 18` and confirms Tornadus/Thundurus/
# Landorus-Therian, Kyurem-Black/White, and Keldeo-Resolute are Black
# 2/White 2-only additions (bw2formeOffset = 35) absent from vanilla BW --
# gated behind items/tutors (Reveal Glass, DNA Splicers, Secret Sword tutor)
# that don't exist in this release.
#
# 13 real, independently-obtainable forms, each with its own PokéDB
# reference file under pokedb/.output/gen5/pokemon/variant/ -- same shape as
# gen4_dppt's PERSONAL_FORM_MEMBERS.
PERSONAL_FORM_MEMBERS: dict[int, str] = {
    650: "deoxys-attack",
    651: "deoxys-defense",
    652: "deoxys-speed",
    653: "wormadam-sandy",
    654: "wormadam-trash",
    655: "shaymin-sky",
    656: "giratina-origin",
    657: "rotom-heat",
    658: "rotom-wash",
    659: "rotom-frost",
    660: "rotom-fan",
    661: "rotom-mow",
    665: "basculin-blue-striped",
}

# 5 battle-only transformations (Castform's weather forms, Darmanitan's Zen
# Mode, Meloetta's Pirouette forme): real distinct stats/types decoded from
# the ROM, but no player independently owns/catches one -- they trigger
# mid-battle via weather/ability/move, and PokéAPI categorizes them
# "transformation" rather than a separately obtainable Pokémon, so PokéDB has
# no dedicated reference page for them. `base_slug` must match the base
# record's own PokéDB-derived slug exactly (verified against the real
# PokéDB JSON `name` fields, which differ from the bare species name for
# Darmanitan/Meloetta).
PERSONAL_TRANSFORMATION_MEMBERS: dict[int, dict[str, str]] = {
    662: {"base_slug": "castform", "label": "Sunny Form"},
    663: {"base_slug": "castform", "label": "Rainy Form"},
    664: {"base_slug": "castform", "label": "Snowy Form"},
    666: {"base_slug": "darmanitan-standard", "label": "Zen Mode"},
    667: {"base_slug": "meloetta-aria", "label": "Pirouette Forme"},
}

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
