from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.marts import (
    SHOP_COUNT,
    parse_mart_dispatch_commands,
    parse_shop_catalog,
)
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script


class HgssMartTests(unittest.TestCase):
    def test_decodes_terminated_shop_catalog(self) -> None:
        locator = b"catalog"
        inventories = [
            struct.pack("<2H", shop_id + 1, 0xFFFF) for shop_id in range(SHOP_COUNT)
        ]
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


class HgssMartDispatchTests(unittest.TestCase):
    def test_decodes_each_mart_dispatch_kind(self) -> None:
        body = (
            struct.pack("<HH", 0x113, 0)
            + struct.pack("<HH", 0x114, 41)
            + struct.pack("<HH", 0x115, 41)
            + struct.pack("<HH", 0x116, 27)
        )

        commands = parse_mart_dispatch_commands(make_script(body))

        self.assertEqual(
            [(c.kind, c.inventory_id) for c in commands],
            [("common", 0), ("specialty", 41), ("decoration", 41), ("seal", 27)],
        )

    def test_ignores_variable_supplied_inventory_selectors(self) -> None:
        body = struct.pack("<HH", 0x113, 0x8004)

        self.assertEqual(parse_mart_dispatch_commands(make_script(body)), ())

    def test_ignores_unrelated_opcodes(self) -> None:
        body = struct.pack("<HH", 0x112, 0)

        self.assertEqual(parse_mart_dispatch_commands(make_script(body)), ())
