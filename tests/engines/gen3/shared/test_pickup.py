from __future__ import annotations

import struct

import pytest

from romwiki.engines.gen3.shared.pickup import (
    parse_pickup_chance_table,
    parse_split_pickup_tables,
)
from romwiki.util.errors import InvalidRomError


def _chance_table(entries: list[tuple[int, int]]) -> bytes:
    return b"".join(struct.pack("<HBx", item, threshold) for item, threshold in entries)


def test_chances_are_the_gaps_between_thresholds_and_the_last_takes_the_rest() -> None:
    thresholds = [15, 25, 35, 45, 55, 65, 75, 80, 85, 90, 95, 96, 97, 98, 99]
    entries = [(10 + index, threshold) for index, threshold in enumerate(thresholds)]
    entries.append((99, 1))

    chances = parse_pickup_chance_table(_chance_table(entries), item_count=400)

    assert [percent for _, percent in chances] == [
        15,
        10,
        10,
        10,
        10,
        10,
        10,
        5,
        5,
        5,
        5,
        1,
        1,
        1,
        1,
        1,
    ]
    assert sum(percent for _, percent in chances) == 100


def test_rejects_falling_thresholds() -> None:
    entries = [(1, 50), (2, 40)] + [(3, 99)] * 14
    with pytest.raises(InvalidRomError):
        parse_pickup_chance_table(_chance_table(entries), item_count=400)


def test_split_tables_read_common_rare_and_rates() -> None:
    tables = parse_split_pickup_tables(
        struct.pack("<18H", *range(1, 19)),
        struct.pack("<11H", *range(30, 41)),
        bytes([30, 40, 50, 60, 70, 80, 90, 94, 98]),
        item_count=400,
    )

    assert tables.common_item_ids[:2] == (1, 2)
    assert tables.rare_item_ids[-1] == 40
    assert tables.common_rate == (30, 40, 50, 60, 70, 80, 90, 94, 98)
    assert tables.honey_gather_rate == ()
