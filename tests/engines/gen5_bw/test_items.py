from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.items import parse_item_record
from romwiki.util.errors import InvalidRomError


class Gen5ItemTests(unittest.TestCase):
    def test_parses_confirmed_fields(self) -> None:
        data = bytearray(36)
        struct.pack_into("<H", data, 0, 400)  # price stored as price/10
        data[2] = 69  # hold_effect_id
        data[4] = 10  # pluck_effect_id
        data[5] = 26  # fling_effect_id
        data[6] = 30  # fling_power

        item = parse_item_record(
            bytes(data),
            item_id=234,
            data_archive_member=234,
            archive_path="itemdata.narc",
        )

        self.assertEqual(item.item_id, 234)
        self.assertEqual(item.data_archive_member, 234)
        self.assertEqual(item.price, 4000)
        self.assertEqual(item.hold_effect_id, 69)
        self.assertEqual(item.pluck_effect_id, 10)
        self.assertEqual(item.fling_effect_id, 26)
        self.assertEqual(item.fling_power, 30)
        self.assertEqual(item.provenance.archive, "itemdata.narc")
        self.assertEqual(item.provenance.member, 234)

    def test_price_is_scaled_by_ten(self) -> None:
        data = bytearray(36)
        struct.pack_into("<H", data, 0, 30)

        item = parse_item_record(
            bytes(data), item_id=17, data_archive_member=17, archive_path="itemdata.narc"
        )

        self.assertEqual(item.price, 300)

    def test_rejects_wrong_record_size(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "must be 36 bytes"):
            parse_item_record(
                b"\0" * 35,
                item_id=1,
                data_archive_member=1,
                archive_path="itemdata.narc",
            )


if __name__ == "__main__":
    unittest.main()
