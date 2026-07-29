from __future__ import annotations

import struct

# Member indices into arc/encdata_ex.narc, Platinum's "extended encounter data"
# archive (separate from fielddata/encountdata/pl_enc_data.narc). Verified against
# the pret/pokeplatinum decompilation's tools/jsoncnv/encdata_ex_*.py converters
# and the res/field/encounters/encdata_ex.order member list.
GEN4_HONEY_TREE_COMMON_MEMBER = 2
GEN4_HONEY_TREE_UNCOMMON_MEMBER = 3
GEN4_HONEY_TREE_RARE_MEMBER = 4
GEN4_TROPHY_GARDEN_MEMBER = 8
GEN4_GREAT_MARSH_POST_NATIONAL_DEX_MEMBER = 9
GEN4_GREAT_MARSH_PRE_NATIONAL_DEX_MEMBER = 10

# Fixed odds baked into HoneyTree_GetTreeEncounterGroup (src/overlay005/honey_tree.c),
# not stored as ROM data. Munchlax trees are a save-file-derived subset of the 21
# honey tree locations; which trees those are is not ROM data either.
GEN4_HONEY_TREE_GROUP_CHANCES = {"common": 70, "uncommon": 20, "rare": 0, "none": 10}
GEN4_HONEY_TREE_MUNCHLAX_GROUP_CHANCES = {
    "common": 20,
    "uncommon": 70,
    "rare": 1,
    "none": 9,
}


def parse_species_list(data: bytes) -> tuple[int, ...]:
    """Parse a flat u32-per-entry species table, as used throughout encdata_ex.narc."""
    count = len(data) // 4
    return struct.unpack_from(f"<{count}I", data, 0)
