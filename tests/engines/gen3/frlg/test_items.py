from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.frlg.items import item_name, parse_item_record
from romwiki.util.errors import InvalidRomError


def _master_ball_record() -> bytes:
    # Mirrors the real FireRed ROM's item 1 record (verified this session):
    # "MASTER BALL", price=0, hold_effect=0, hold_effect_parameter=0,
    # field_pocket_id=3 (poke-balls).
    data = bytearray(44)
    name = bytes(
        (0xC7, 0xBB, 0xCD, 0xCE, 0xBF, 0xCC, 0x00, 0xBC, 0xBB, 0xC6, 0xC6, 0xFF)
    )
    data[0 : len(name)] = name
    struct.pack_into("<H", data, 0x0E, 1)  # item_id
    struct.pack_into("<H", data, 0x10, 0)  # price
    data[0x12] = 0
    data[0x13] = 0
    data[0x1A] = 3
    return bytes(data)


class Gen3ItemDataTests(unittest.TestCase):
    def test_decodes_name_price_hold_effect_and_pocket(self) -> None:
        data = _master_ball_record()

        name = item_name(data)
        record = parse_item_record(data, item_id=1, archive_path="offset:0x0")

        self.assertEqual(name, "MASTER BALL")
        self.assertEqual(record.item_id, 1)
        self.assertEqual(record.price, 0)
        self.assertEqual(record.hold_effect_id, 0)
        self.assertEqual(record.hold_effect_parameter, 0)
        self.assertEqual(record.field_pocket_id, 3)
        # Fling/Pluck don't exist in Generation III.
        self.assertEqual(record.fling_effect_id, 0)
        self.assertEqual(record.fling_power, 0)
        self.assertEqual(record.pluck_effect_id, 0)
        self.assertIsNone(record.party_effects)
        self.assertFalse(record.party_use)
        self.assertEqual(record.provenance.member, 1)
        self.assertEqual(record.provenance.archive, "offset:0x0")
        self.assertEqual(record.provenance.source, "rom")

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_item_record(b"short", item_id=1, archive_path="offset:0x0")


if __name__ == "__main__":
    unittest.main()
