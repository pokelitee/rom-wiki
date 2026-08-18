from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.events import Gen4ObjectEvent
from romwiki.engines.gen4.hgss.events import (
    parse_item_ball_table,
    resolve_visible_item_id,
)

_SCRIPT_TABLE_END = 0xFD13


def _build_item_ball_table_script(entries: list[tuple[int, int]]) -> bytes:
    """Build a minimal Gen IV script with one `SetVarFromVar`+End function per entry.

    Mirrors the real HGSS item-ball table's own shape (see
    `gen4/hgss/events.py`'s module docstring): each function stages an item
    ID and quantity into the two scratch variables the table's shared
    give-item tail reads, then returns.
    """
    function_size = 14  # two 6-byte SetVarFromVar instructions + 2-byte End
    table_size = len(entries) * 4 + 2  # one offset per entry, plus terminator
    code = b""
    offsets = b""
    for index, (item_id, quantity) in enumerate(entries):
        function_start = table_size + index * function_size
        cursor = index * 4
        relative = function_start - (cursor + 4)
        offsets += struct.pack("<i", relative)
        code += (
            struct.pack("<HHH", 0x29, 32776, item_id)
            + struct.pack("<HHH", 0x29, 32777, quantity)
            + struct.pack("<H", 0x2)
        )
    return offsets + struct.pack("<H", _SCRIPT_TABLE_END) + code


class HGSSItemBallTableTests(unittest.TestCase):
    def test_decodes_item_and_quantity_by_function_index(self) -> None:
        data = _build_item_ball_table_script([(433, 1), (17, 1)])

        table = parse_item_ball_table(data)

        self.assertEqual(table, (433, 17))

    def test_resolves_visible_item_through_the_table_not_a_flat_offset(self) -> None:
        # `script_id - 7000` is `0` for this event, but the table entry at
        # index 0 gives item 433 -- the real HGSS mechanism, not a flat
        # `script_id - 7000 = item_id` shortcut (which would wrongly give
        # item 0, an invalid/no-item sentinel, or a coincidentally different
        # real item if a hack repurposed the entry).
        table = parse_item_ball_table(_build_item_ball_table_script([(433, 1)]))
        event = Gen4ObjectEvent(
            index=0,
            local_id=0,
            graphics_id=87,
            movement_type=0,
            trainer_type=0,
            hidden_flag=0,
            script_id=7000,
            direction=0,
            data=(0, 0, 0),
            movement_range_x=0,
            movement_range_z=0,
            x=0,
            z=0,
            y=0,
        )

        self.assertEqual(
            resolve_visible_item_id(event, item_count=600, item_ids=table), 433
        )

    def test_returns_none_for_an_out_of_range_table_index(self) -> None:
        table = parse_item_ball_table(_build_item_ball_table_script([(433, 1)]))
        event = Gen4ObjectEvent(
            index=0,
            local_id=0,
            graphics_id=87,
            movement_type=0,
            trainer_type=0,
            hidden_flag=0,
            script_id=7001,
            direction=0,
            data=(0, 0, 0),
            movement_range_x=0,
            movement_range_z=0,
            x=0,
            z=0,
            y=0,
        )

        self.assertIsNone(
            resolve_visible_item_id(event, item_count=600, item_ids=table)
        )


if __name__ == "__main__":
    unittest.main()
