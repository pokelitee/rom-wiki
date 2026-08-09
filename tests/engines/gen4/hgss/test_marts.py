from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.marts import SHOP_COUNT, parse_shop_catalog
from romwiki.util.errors import InvalidRomError


class HgssMartTests(unittest.TestCase):
    def test_decodes_terminated_shop_catalog(self) -> None:
        locator = b"catalog"
        inventories = [struct.pack("<2H", shop_id + 1, 0xFFFF) for shop_id in range(SHOP_COUNT)]
        shops = parse_shop_catalog(
            locator + b"".join(inventories),
            locator=locator,
            archive_path="arm9",
            item_count=537,
        )

        self.assertEqual(len(shops), 27)
        self.assertEqual(shops[0].shop_id, 0)
        self.assertEqual(shops[0].item_ids, (1,))

    def test_rejects_unterminated_catalog(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_shop_catalog(
                b"catalog" + b"\x01\x00",
                locator=b"catalog",
                archive_path="arm9",
                item_count=537,
            )
