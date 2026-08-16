"""TM/HM machine-numbering facts shared by both BW and B2W2.

Both games' ARM9 machine table -- and every Pokemon's TM/HM compatibility
bitmap, which is indexed by that same table's physical layout -- interleaves
TM01-92, then HM01-06, then TM93-95. The published, contiguous numbering
(TM01-95 -> 1-95, HM01-06 -> 96-101) is this project's own presentation
choice, so any code translating between the two needs this mapping.
"""

from __future__ import annotations

GEN5_TM_BLOCK_ONE_COUNT = 92
GEN5_HM_COUNT = 6
GEN5_TM_COUNT = 95
_BLOCK_TWO_START = GEN5_TM_BLOCK_ONE_COUNT + GEN5_HM_COUNT


def machine_id_for_table_index(index: int) -> int:
    """Map a machine's physical ARM9 table/bitmap position (0-based) to its
    published, contiguous machine ID.
    """
    if index < GEN5_TM_BLOCK_ONE_COUNT:
        return index + 1
    if index < _BLOCK_TWO_START:
        return GEN5_TM_COUNT + (index - GEN5_TM_BLOCK_ONE_COUNT) + 1
    return GEN5_TM_BLOCK_ONE_COUNT + (index - _BLOCK_TWO_START) + 1
