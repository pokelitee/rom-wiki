from __future__ import annotations

import struct

from romwiki.schema import Gen5PickupTable, RecordProvenance
from romwiki.util.errors import InvalidRomError

# `Gen5Constants.pickupTableLocator`/`numberOfPickupItems`
# (Ajarmar/universal-pokemon-randomizer-zx): a 29-word item table found by
# byte-pattern search in the `PickupOvlNumber` overlay, since -- like the
# TM/HM move table -- it has no stable absolute offset across ROM builds.
PICKUP_TABLE_LOCATOR = "19005C00DD00"
PICKUP_ITEM_COUNT = 29
PICKUP_LEVEL_RANGE_COUNT = 10
PICKUP_LEVEL_RANGE_SIZE = 10

# `Gen5RomHandler.getPickupItems()`'s own hardcoded per-level-range formula:
# for level range `r` (0-9, i.e. levels 10r+1..10r+10), the "common" pool is
# table entries [11+r .. 19+r] (a 9-item window that slides by one entry per
# range) and the "rare" pool is entries [r, r+1] (a 2-item window) -- these
# percentages themselves aren't ROM data, they're a fixed engine constant
# (the same 30/10x6/4/4/1/1 formula used since Generation IV's Pickup).
# Order matches the item order this module returns for each level range.
PICKUP_SLOT_CHANCES = (30, 10, 10, 10, 10, 10, 10, 4, 4, 1, 1)


def parse_pickup_table(
    overlay_data: bytes, *, table_offset: int, archive_path: str
) -> Gen5PickupTable:
    size = PICKUP_ITEM_COUNT * 2
    if table_offset < 0 or table_offset + size > len(overlay_data):
        raise InvalidRomError("Gen V pickup item table is outside the overlay")
    item_ids = struct.unpack_from(f"<{PICKUP_ITEM_COUNT}H", overlay_data, table_offset)
    return Gen5PickupTable(
        item_ids=item_ids,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=table_offset
        ),
    )


def pickup_level_range_item_ids(
    item_ids: tuple[int, ...], level_range: int
) -> tuple[int, ...]:
    """Return the 11 item IDs for one level range, in `PICKUP_SLOT_CHANCES` order."""
    common_offset = 11 + level_range
    rare_offset = level_range
    return (
        *item_ids[common_offset : common_offset + 9],
        item_ids[rare_offset],
        item_ids[rare_offset + 1],
    )
