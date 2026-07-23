from __future__ import annotations

import struct

from romwiki.schema.pickup import Gen4PickupTables
from romwiki.util.errors import InvalidRomError


def parse_pickup_tables(
    data: bytes,
    *,
    common_offset: int,
    rare_offset: int,
    common_rate_offset: int,
    honey_rate_offset: int,
    common_count: int,
    rare_count: int,
    rate_count: int,
    honey_rate_count: int,
    item_count: int,
) -> Gen4PickupTables:
    return Gen4PickupTables(
        common_item_ids=_item_ids(
            data, common_offset, common_count, item_count, "Common Pickup"
        ),
        rare_item_ids=_item_ids(
            data, rare_offset, rare_count, item_count, "Rare Pickup"
        ),
        common_rate=_rates(data, common_rate_offset, rate_count),
        honey_gather_rate=_rates(data, honey_rate_offset, honey_rate_count),
    )


def _item_ids(
    data: bytes, offset: int, count: int, item_count: int, label: str
) -> tuple[int, ...]:
    size = count * 2
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError(f"{label} item table is outside the overlay")
    item_ids = struct.unpack_from(f"<{count}H", data, offset)
    for item_id in item_ids:
        if not 0 < item_id < item_count:
            raise InvalidRomError(f"{label} table references invalid item {item_id}")
    return item_ids


def _rates(data: bytes, offset: int, count: int) -> tuple[int, ...]:
    if offset < 0 or offset + count > len(data):
        raise InvalidRomError("Pickup rate table is outside the overlay")
    return tuple(data[offset : offset + count])
