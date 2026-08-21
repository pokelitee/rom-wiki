"""TM/HM machine-table numbering shared by both BW and B2W2.

Both games' ARM9 move table interleaves TM01-92, HM01-06, then TM93-95.
Personal-data compatibility bitmaps instead use the published TM01-95,
HM01-06 order and must not use this table-index mapping.
"""

from __future__ import annotations

GEN5_TM_BLOCK_ONE_COUNT = 92
GEN5_HM_COUNT = 6
GEN5_TM_COUNT = 95
_BLOCK_TWO_START = GEN5_TM_BLOCK_ONE_COUNT + GEN5_HM_COUNT


def machine_id_for_table_index(index: int) -> int:
    """Map a physical ARM9 move-table index to a contiguous machine ID."""
    if index < GEN5_TM_BLOCK_ONE_COUNT:
        return index + 1
    if index < _BLOCK_TWO_START:
        return GEN5_TM_COUNT + (index - GEN5_TM_BLOCK_ONE_COUNT) + 1
    return GEN5_TM_BLOCK_ONE_COUNT + (index - _BLOCK_TWO_START) + 1
