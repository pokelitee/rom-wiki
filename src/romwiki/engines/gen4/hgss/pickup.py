from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

PICKUP_COMMON_TABLE_LOCATOR = "110012001A000300"
PICKUP_RARE_TABLE_LOCATOR = "19005C00DD00"
PICKUP_COMMON_ITEM_COUNT = 18
PICKUP_RARE_ITEM_COUNT = 11
PICKUP_LEVEL_RANGE_COUNT = 10
PICKUP_LEVEL_RANGE_SIZE = 10
PICKUP_SLOT_CHANCES = (30, 10, 10, 10, 10, 10, 10, 4, 4, 1, 1)


def parse_pickup_item_table(
    data: bytes, *, offset: int, count: int, item_count: int
) -> tuple[int, ...]:
    size = count * 2
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError("HGSS Pickup item table is outside its overlay")
    item_ids = struct.unpack_from(f"<{count}H", data, offset)
    if any(not 0 < item_id < item_count for item_id in item_ids):
        raise InvalidRomError("HGSS Pickup table references an invalid item")
    return item_ids


def pickup_level_range_item_ids(
    common_item_ids: tuple[int, ...],
    rare_item_ids: tuple[int, ...],
    level_range: int,
) -> tuple[int, ...]:
    if not 0 <= level_range < PICKUP_LEVEL_RANGE_COUNT:
        raise InvalidRomError("HGSS Pickup level range is invalid")
    if (
        len(common_item_ids) != PICKUP_COMMON_ITEM_COUNT
        or len(rare_item_ids) != PICKUP_RARE_ITEM_COUNT
    ):
        raise InvalidRomError("HGSS Pickup item counts are invalid")
    return (
        *common_item_ids[level_range : level_range + 9],
        *rare_item_ids[level_range : level_range + 2],
    )
