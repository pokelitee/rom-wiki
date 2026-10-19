"""Generation V facts identical in Black/White and Black 2/White 2."""

from __future__ import annotations

# National Pokédex species introduced through Generation V.
GEN5_BASE_SPECIES_COUNT = 649

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
# includes a leading placeholder entry (index 0).
MOVE_NAME_COUNT = 560
ABILITY_NAME_COUNT = 165

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
# Generation IV's own scheme (see gen4_platinum's EVOLUTION_METHOD_NAMES) except
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

# Generation V personal archives are indexed by National Dex ID, and ability
# IDs match PokéDB's.
INTERNAL_TO_NATIONAL_DEX: dict[int, int] = {}
ABILITY_REFERENCE_IDS: dict[int, int | None] = {}
