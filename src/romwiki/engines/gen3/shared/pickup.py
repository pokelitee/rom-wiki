"""Generation III Pickup tables, per pret's `src/battle_script_commands.c`.

Emerald keeps Generation IV's split shape: 18 common items, 11 rare items,
and nine cumulative percentage thresholds, the window sliding by a tenth of
the Pokémon's level. FireRed/LeafGreen instead roll once against 16
`(item, threshold)` entries: the first item whose threshold exceeds a
0-99 roll, or the last item when none does (`GetPickupItem` only checks the
first 15). Both games trigger Pickup on 10% of battles.
"""

from __future__ import annotations

import struct

from romwiki.schema import SplitPickupTable
from romwiki.util.errors import InvalidRomError

PICKUP_COMMON_ITEM_COUNT = 18
PICKUP_RARE_ITEM_COUNT = 11
PICKUP_COMMON_RATE_COUNT = 9
PICKUP_CHANCE_ITEM_COUNT = 16
# `struct PickupItem`: u16 item, u8 threshold, one byte of padding.
PICKUP_CHANCE_ENTRY_SIZE = 4
_PERCENT = 100


def parse_split_pickup_tables(
    common: bytes, rare: bytes, rates: bytes, *, item_count: int
) -> SplitPickupTable:
    common_ids = _item_ids(common, PICKUP_COMMON_ITEM_COUNT, item_count)
    rare_ids = _item_ids(rare, PICKUP_RARE_ITEM_COUNT, item_count)
    if len(rates) != PICKUP_COMMON_RATE_COUNT or list(rates) != sorted(rates):
        raise InvalidRomError("Gen III Pickup rates must be nine rising thresholds")
    return SplitPickupTable(
        common_item_ids=common_ids,
        rare_item_ids=rare_ids,
        common_rate=tuple(rates),
        honey_gather_rate=(),
    )


def parse_pickup_chance_table(
    data: bytes, *, item_count: int
) -> tuple[tuple[int, int], ...]:
    """`(item, percent)` for each entry, from its cumulative threshold."""
    if len(data) != PICKUP_CHANCE_ITEM_COUNT * PICKUP_CHANCE_ENTRY_SIZE:
        raise InvalidRomError("Gen III Pickup table has the wrong size")
    entries = [
        struct.unpack_from("<HB", data, index * PICKUP_CHANCE_ENTRY_SIZE)
        for index in range(PICKUP_CHANCE_ITEM_COUNT)
    ]
    thresholds = [threshold for _, threshold in entries[:-1]]
    if thresholds != sorted(thresholds) or thresholds[-1] > _PERCENT:
        raise InvalidRomError("Gen III Pickup thresholds must rise to at most 100")
    result = []
    previous = 0
    for index, (item_id, threshold) in enumerate(entries):
        if not 0 < item_id < item_count:
            raise InvalidRomError(f"Gen III Pickup entry {index} has item {item_id}")
        upper = threshold if index < len(entries) - 1 else _PERCENT
        result.append((item_id, upper - previous))
        previous = upper
    return tuple(result)


def _item_ids(data: bytes, count: int, item_count: int) -> tuple[int, ...]:
    if len(data) != count * 2:
        raise InvalidRomError("Gen III Pickup item table has the wrong size")
    ids = struct.unpack(f"<{count}H", data)
    if not all(0 < item_id < item_count for item_id in ids):
        raise InvalidRomError("Gen III Pickup item table has an invalid item")
    return tuple(ids)
