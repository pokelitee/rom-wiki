from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.marts import parse_archive_shop_catalog


class B2W2MartTests(unittest.TestCase):
    def test_decodes_archive_inventory_with_engine_metadata(self) -> None:
        members = [b""] * 32
        members[7] = struct.pack("<2H", 331, 335)

        shops = parse_archive_shop_catalog(members, archive_path="a/2/8/2")

        striaton = next(shop for shop in shops if shop.shop_id == 7)
        self.assertEqual(striaton.name, "Striaton Secondary (TMs)")
        self.assertEqual(striaton.kind, "tm")
        self.assertEqual(striaton.item_ids, (331, 335))
        self.assertEqual(striaton.provenance.archive, "a/2/8/2")
        self.assertNotIn(0, {shop.shop_id for shop in shops})


if __name__ == "__main__":
    unittest.main()
