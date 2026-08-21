from __future__ import annotations

# Struct shapes/fixed tables shared with FireRed/LeafGreen live in
# `gen3/shared/constants.py`. Everything below is Emerald-specific: either
# a real per-game record count (differs from FireRed/LeafGreen's own
# counts) or a domain not yet implemented for this leaf.

# Zero rather than a guessed count for domains not yet implemented on this
# leaf.
POKEMON_NAME_COUNT = 0
POKEMON_DESCRIPTION_COUNT = 0

# `sAbilityNames`/`sAbilityDescriptionPointers`: verified against the real
# Emerald ROM -- identical 78-entry table to FireRed/LeafGreen's (index 0
# placeholder, index 1 "STENCH" ... index 77 "AIR LOCK", index 76
# "CACOPHONY"), same real/PokeDB numbering divergence at Cacophony.
ABILITY_NAME_COUNT = 76

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
