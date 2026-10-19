from __future__ import annotations

# Struct shapes/fixed tables shared with FireRed/LeafGreen live in
# `gen3/shared/constants.py`. Everything below is Emerald-specific: either
# a real per-game record count (differs from FireRed/LeafGreen's own
# counts) or a domain not yet implemented for this leaf.

# `gSpeciesNames`: one 11-byte name per personal record, as on FireRed/
# LeafGreen. Pokédex entries come from PokéDB rather than the ROM.
POKEMON_NAME_COUNT = 412
POKEMON_DESCRIPTION_COUNT = 0

# `sAbilityNames`/`sAbilityDescriptionPointers`: verified against the real
# Emerald ROM -- identical 78-entry table to FireRed/LeafGreen's (index 0
# placeholder, index 1 "STENCH" ... index 76 "CACOPHONY", index 77 "AIR
# LOCK"); see `ABILITY_REFERENCE_IDS` for the PokéDB numbering.
ABILITY_NAME_COUNT = 78

# Index 0 is an all-"?" placeholder. Real item count differs from FireRed/
# LeafGreen's (374) -- Emerald's own item list runs through index 376
# ("OLD SEA MAP", the last real item; Emerald-exclusive items include
# "MAGMA EMBLEM" and "OLD SEA MAP", which FireRed/LeafGreen don't have).
ITEM_RECORD_COUNT = 377
ITEM_NAME_COUNT = 377

# Verified against the real Emerald ROM: found real trainers (e.g. Team
# Aqua/Magma "GRUNT" trainers, "SAWYER", "MAY") with the same struct shape,
# stride, and flags scheme as FireRed/LeafGreen's. Real count differs
# (FireRed/LeafGreen 743) -- Emerald's own trainer table runs through
# index 854.
TRAINER_RECORD_COUNT = 855

# Classes 0 ("PKMN TRAINER") through 65; trainers use 0-65.
TRAINER_CLASS_COUNT = 66

# `gTutorMoves`: FireRed/LeafGreen's 15 tutor moves followed by 15 more, each
# with a bit in a species' 4-byte `sTutorLearnsets` mask.
TUTOR_MOVE_COUNT = 30
TUTOR_COMPATIBILITY_SIZE = 4

# Ten tutors are field NPCs whose scripts reach the tutor routine the way
# FireRed/LeafGreen's do (see `gen3/frlg/constants.py`'s `TUTOR_LOCATIONS`):
# each script starts 54 bytes before its `setvar VAR_0x8005, <index>`. The
# other twenty are the Battle Frontier's: their moves are exactly the two
# 10-move lists read by specials 474 and 475, which only a Battle Frontier
# NPC's script calls.
TUTOR_LOCATIONS = {
    0: "Battle Frontier",  # Mega Punch
    1: "Battle Frontier",  # Swords Dance
    2: "Battle Frontier",  # Mega Kick
    3: "Battle Frontier",  # Body Slam
    4: "Sootopolis City",  # Double-Edge
    5: "Battle Frontier",  # Counter
    6: "Battle Frontier",  # Seismic Toss
    7: "Lavaridge Town",  # Mimic
    8: "Fallarbor Town",  # Metronome
    9: "Battle Frontier",  # Softboiled
    10: "Battle Frontier",  # Dream Eater
    11: "Battle Frontier",  # Thunder Wave
    12: "Pacifidlog Town",  # Explosion
    13: "Battle Frontier",  # Rock Slide
    14: "Lilycove City",  # Substitute
    15: "Mossdeep City",  # DynamicPunch
    16: "Mauville City",  # Rollout
    17: "Battle Frontier",  # Psych Up
    18: "Battle Frontier",  # Snore
    19: "Battle Frontier",  # Icy Wind
    20: "Battle Frontier",  # Endure
    21: "Battle Frontier",  # Mud-Slap
    22: "Battle Frontier",  # Ice Punch
    23: "Slateport City",  # Swagger
    24: "Fortree City",  # Sleep Talk
    25: "Battle Frontier",  # Swift
    26: "Battle Frontier",  # Defense Curl
    27: "Battle Frontier",  # ThunderPunch
    28: "Battle Frontier",  # Fire Punch
    29: "Verdanturf Town",  # Fury Cutter
}

# `gWildMonHeaders`: verified against the real Emerald ROM -- struct shape
# and slot counts are the shared Gen III fact (`gen3/shared/constants.py`'s
# `ENCOUNTER_HEADER_SIZE`); this leaf's table offset/count are its own.
# Header 0 (mapGroup 0/mapNum 16) decodes to Wurmple/Poochyena/Zigzagoon,
# Route 101's real land encounters; header 1 (mapNum 17) includes Ralts,
# Route 102's well-known Emerald-exclusive encounter -- confirming both the
# struct layout and the table location. Terminated by a {0xFF, 0xFF, ...}
# sentinel immediately after entry 123, same convention as FireRed/
# LeafGreen. Real count differs from FireRed/LeafGreen's 132.
ENCOUNTER_HEADER_COUNT = 124

# `gMapGroups`: 34 groups (518 maps), found as the pointer table whose
# entries point at each group's map-header pointer array; every map's
# region section resolves to a Town Map name (Route 101, Petalburg Woods,
# Battle Frontier, ...). A hack that adds groups sets `map_group_count`.
GMAPGROUPS_GROUP_COUNT = 34

# `gRegionMapEntries`: one 8-byte entry per region map section, starting at
# section 0, with the section's name pointer at +4 (`struct RegionMapLocation`).
# Several sections share one string (each "UNDERWATER" section points at the
# same name), so the names can't be read back-to-back.
REGION_NAME_ENTRY_SIZE = 8
REGION_NAME_POINTER_OFFSET = 4
FIRST_REGION_MAP_SECTION = 0

# `gSpecials` index of `CreateEnemyEventMon`, which `seteventmon` calls to
# set up an event legendary's battle. Every Emerald call site is preceded by
# `setvar` of the species, level, and item.
EVENT_MON_SPECIAL = 482

# `gSpecials` index of `GetInGameTradeSpeciesInfo`, which a trader's script
# calls after setting `VAR_0x8008` to the trade's index.
TRADE_INFO_SPECIAL = 255
