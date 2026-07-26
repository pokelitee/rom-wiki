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

# Trainer-party form operands that select a battle form with its own
# personal record; slugs match the PERSONAL_FORM_MEMBERS entries above.
# Retail Black uses only Wormadam and Basculin here. Blaze Black/Volt White
# additionally use every Rotom appliance form in trainer parties.
TRAINER_FORM_SLUGS: dict[tuple[int, int], str] = {
    (413, 1): "wormadam-sandy",
    (413, 2): "wormadam-trash",
    (479, 1): "rotom-heat",
    (479, 2): "rotom-wash",
    (479, 3): "rotom-frost",
    (479, 4): "rotom-fan",
    (479, 5): "rotom-mow",
    (550, 1): "basculin-blue-striped",
}

# Shellos and Gastrodon's East Sea forms reuse their base personal records.
# They do not appear in retail Black's trainer parties, but both hacks use
# them with the same Gen V form operand used by the game elsewhere.
TRAINER_COSMETIC_FORM_LABELS: dict[tuple[int, int], str] = {
    (422, 1): "East Sea",
    (423, 1): "East Sea",
}

# TM01-95, HM01-06 (Gen5Constants.tmCount / hmCount, Ajarmar/universal-pokemon-randomizer-zx).
GEN5_TM_COUNT = 95
GEN5_HM_COUNT = 6
GEN5_MACHINE_COUNT = GEN5_TM_COUNT + GEN5_HM_COUNT

# The real ARM9 table (found via GEN5_MACHINE_TABLE_PREFIX below) isn't TM1-95
# followed by HM1-6 -- it's TM01-92, then HM01-06, then TM93-95, confirmed
# against real Black ROM data: TM01=Hone Claws, TM92=Trick Room, HM01=Cut,
# HM06=Dive, TM93=Wild Charge, TM95=Snarl (Gen5RomHandler.java's
# `getTMMoves`/`getHMMoves` read the same three blocks in this order).
GEN5_TM_BLOCK_ONE_COUNT = 92
# Item IDs for the TM/HM item that teaches each machine -- confirmed against
# the real ROM's own item-name table (`a/0/0/2` member 54): TM01=item 328,
# TM92=419, HM01=420, HM06=425, TM93=618, TM95=620. TM01-92 and HM01-06 share
# Generation IV's exact item ID scheme; TM93-95 are new Generation V items
# with their own separate block.
GEN5_TM_BLOCK_ONE_ITEM_ID_OFFSET = 327
GEN5_HM_ITEM_ID_OFFSET = 419
GEN5_TM_BLOCK_TWO_ITEM_ID_BASE = 618

# Byte-pattern prefix immediately preceding the TM/HM move-ID table in the
# decompressed ARM9 binary (Gen5Constants.tmDataPrefix,
# Ajarmar/universal-pokemon-randomizer-zx); confirmed unique in a real
# Black ROM's decompressed ARM9.
GEN5_MACHINE_TABLE_PREFIX = "87038803"

# Byte-order type table (Gen5Constants.constructTypeTable(), Ajarmar/universal-
# pokemon-randomizer-zx); confirmed against a real Black ROM record (Bulbasaur
# decodes to grass=11/poison=3 at this table's indices). No Fairy type yet and,
# unlike Gen4, no reserved "unknown" placeholder slot.
TYPE_NAME_COUNT = 17
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
    "fire",
    "water",
    "grass",
    "electric",
    "psychic",
    "ice",
    "dragon",
    "dark",
)

# Unchanged from earlier generations' identical engine-internal ID schemes;
# confirmed against a real Black ROM record (Bulbasaur: egg groups
# monster/grass, growth rate medium-slow, color green all decode correctly
# against these tables).
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

# Name-table entry counts, confirmed empirically by decoding every entry in
# a real Black ROM's `a/0/0/2` (TextStrings) NARC -- see messages.py. Each
# includes a leading placeholder entry (index 0) and, for Pokémon, two
# trailing "Egg" entries (650-651) alongside the 649 real species.
MOVE_NAME_COUNT = 560
ABILITY_NAME_COUNT = 165
ITEM_NAME_COUNT = 627
POKEMON_NAME_COUNT = 652

# Move data archive `a/0/2/1` (a different table from the move *names* text
# above): confirmed empirically against a real Black ROM to hold 560 members
# (member 0 an unused placeholder, members 1-559 the real moves -- matches
# Gen5Constants.java's authoritative `moveCount = 559`,
# Ajarmar/universal-pokemon-randomizer-zx), byte-for-byte identical to White's
# copy of the same archive.
MOVE_RECORD_SIZE = 36
MOVE_RECORD_COUNT = 560
MAX_MOVE_ID = 559

# Gen5Constants.java's `moveCategoryIndices = { STATUS, PHYSICAL, SPECIAL }`
# (Ajarmar/universal-pokemon-randomizer-zx); confirmed against real Black ROM
# records (Toxic/Thunder Wave/Swords Dance/Growl decode to status, Body
# Slam/Quick Attack to physical, Flamethrower/Thunderbolt/Ice Beam to special).
DAMAGE_CLASS_NAMES = ("status", "physical", "special")

# Evolution table `a/0/1/9`: 42-byte record (7 slots x 6 bytes, no padding),
# indexed 1:1 with the personal archive (member 0 is an all-zero placeholder).
EVOLUTION_RECORD_SIZE = 42
EVOLUTION_SLOT_COUNT = 7
EVOLUTION_SLOT_SIZE = 6

# EvolutionType.java's per-generation index table (Ajarmar/universal-pokemon-
# randomizer-zx) gives Generation V's evolution-method IDs: identical to
# Generation IV's own scheme (see gen4_dppt's EVOLUTION_METHOD_NAMES) except
# for one new method -- "trade-special" -- inserted at index 7, shifting
# every method from "use-item" onward up by one. Confirmed against a real
# Black ROM: Tyrogue's three evolutions decode to methods 9/10/11 (attack-
# greater/atk-def-same/defense-greater -> Hitmonlee/Hitmontop/Hitmonchan),
# Eevee's stone evolutions to method 8 (use-item) with parameter = item ID,
# Snorunt's Dawn Stone evolution to method 18 (use-item-female), and Eevee's
# Leafeon/Glaceon evolutions to methods 26/27 (level-moss-rock/level-icy-rock).
EVOLUTION_METHOD_NAMES = (
    "none",
    "friendship",
    "friendship-day",
    "friendship-night",
    "level",
    "trade",
    "trade-held-item",
    "trade-special",
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
    **dict.fromkeys((4, 9, 10, 11, 14, 15, 23), "level"),
    **dict.fromkeys((6, 8, 17, 18, 19, 20), "item"),
    12: "personality",
    13: "personality",
    16: "beauty",
    21: "move",
    22: "pokemon",
}
