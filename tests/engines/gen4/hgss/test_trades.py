from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.trades import parse_npc_trade_record
from romwiki.util.errors import InvalidRomError


class HgssTradeTests(unittest.TestCase):
    def test_decodes_trade_record(self) -> None:
        values = [95, 25, 20, 18, 31, 13, 5, 5, 48926]
        values.extend([0, 0, 0, 0, 0, 9711, 156, 0, 0, 2, 69, 0])
        record = parse_npc_trade_record(
            struct.pack("<21I", *values),
            trade_id=0,
            nickname="Rocky",
            ot_name="Muscle",
            archive_path="a/1/1/2",
        )

        self.assertEqual(record.offered_species_id, 95)
        self.assertEqual(record.requested_species_id, 69)
        self.assertEqual(record.ivs, (25, 20, 18, 13, 5, 31))
        self.assertEqual(record.ot_id, 48926)
        self.assertEqual(record.held_item_id, 156)

    def test_rejects_nonzero_trailing_padding(self) -> None:
        values = [95, 25, 20, 25, 15, 15, 15, 5, 48926]
        values.extend([0, 0, 0, 0, 0, 9711, 156, 0, 0, 2, 69, 1])
        with self.assertRaises(InvalidRomError):
            parse_npc_trade_record(
                struct.pack("<21I", *values),
                trade_id=0,
                nickname="Rocky",
                ot_name="Muscle",
                archive_path="a/1/1/2",
            )
