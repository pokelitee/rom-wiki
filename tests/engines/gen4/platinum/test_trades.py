from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import (
    parse_npc_trade_commands,
    parse_npc_trade_record,
)
from romwiki.util.errors import InvalidRomError


def make_trade_record() -> bytes:
    return struct.pack(
        "<20I",
        363,
        31,
        31,
        15,
        15,
        31,
        15,
        28,
        25643,
        0,
        0,
        0,
        0,
        0,
        142,
        246,
        1,
        50,
        2,
        77,
    )


def make_script_table_prefix() -> bytes:
    """A minimal valid script table pointing code at offset 4."""
    return struct.pack("<i", 0)


class Gen4NpcTradeTests(unittest.TestCase):
    def test_parses_trade_record(self) -> None:
        trade = parse_npc_trade_record(
            make_trade_record(), species_count=494, item_count=537
        )

        self.assertEqual(trade.offered_species_id, 363)
        self.assertEqual(trade.requested_species_id, 77)
        self.assertEqual(trade.ivs, (31, 31, 15, 31, 15, 15))
        self.assertEqual(trade.ot_id, 25643)
        self.assertEqual(trade.personality, 142)
        self.assertEqual(trade.nature, "Quiet")
        self.assertEqual(trade.held_item_id, 246)
        self.assertEqual(trade.ot_gender, 1)
        self.assertEqual(trade.language_id, 2)
        self.assertEqual(trade.contest_stats, (0, 0, 0, 0, 0))
        self.assertEqual(trade.unused_values, (28, 50))

    def test_rejects_invalid_record_size(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "Expected 80 bytes"):
            parse_npc_trade_record(b"\0" * 79, species_count=494, item_count=537)

    def test_extracts_signed_trade_sequence(self) -> None:
        command = make_script_table_prefix() + (
            struct.pack("<HB", 0x0226, 2)
            + struct.pack("<HH", 0x0029, 0x8004)
            + struct.pack("<HH", 0x0228, 0x800C)
            + struct.pack("<HHH", 0x0229, 0x8004, 0x022A)
        )

        self.assertEqual(
            [
                (result.offset, result.trade_id)
                for result in parse_npc_trade_commands(command, trade_count=4)
            ],
            [(4, 2)],
        )

    def test_ignores_initializer_without_trade_sequence(self) -> None:
        command = make_script_table_prefix() + struct.pack(
            "<HBHHH", 0x0226, 2, 0x0228, 0x800C, 0x022A
        )
        self.assertEqual(parse_npc_trade_commands(command, trade_count=4), ())


if __name__ == "__main__":
    unittest.main()
