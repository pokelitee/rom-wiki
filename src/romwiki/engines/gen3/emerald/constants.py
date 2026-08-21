from __future__ import annotations

# Struct shapes/fixed tables shared with FireRed/LeafGreen live in
# `gen3/shared/constants.py`. Everything below is Emerald-specific: either
# a real per-game record count (differs from FireRed/LeafGreen's own
# counts) or a domain not yet implemented for this leaf.

# Zero rather than a guessed count for domains not yet implemented on this
# leaf.
ITEM_NAME_COUNT = 0
POKEMON_NAME_COUNT = 0
POKEMON_DESCRIPTION_COUNT = 0

# `sAbilityNames`/`sAbilityDescriptionPointers`: verified against the real
# Emerald ROM -- identical 78-entry table to FireRed/LeafGreen's (index 0
# placeholder, index 1 "STENCH" ... index 77 "AIR LOCK", index 76
# "CACOPHONY"), same real/PokeDB numbering divergence at Cacophony.
ABILITY_NAME_COUNT = 76
