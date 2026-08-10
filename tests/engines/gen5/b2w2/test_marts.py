from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.marts import (
    parse_archive_shop_catalog,
    resolve_location_special_vendors,
    resolve_special_vendor,
)


class B2W2MartTests(unittest.TestCase):
    def test_resolves_sequel_bp_exchange_prices(self) -> None:
        tm_exchange = resolve_special_vendor(253)
        item_exchange = resolve_special_vendor(254)

        self.assertEqual(
            (tm_exchange.items[0].item_id, tm_exchange.items[0].price), (344, 6)
        )
        self.assertIn(
            (82, 3), {(item.item_id, item.price) for item in item_exchange.items}
        )
        self.assertIn(
            (50, 24), {(item.item_id, item.price) for item in item_exchange.items}
        )
        self.assertIsNone(resolve_special_vendor(247))

    def test_resolves_all_black_city_market_states(self) -> None:
        stores = resolve_location_special_vendors(5)

        self.assertEqual(len(stores), 4)
        self.assertEqual(
            [(item.item_id, item.price, item.availability) for item in stores[0].items],
            [(83, 10000, "Weekdays"), (321, 10000, "Weekends")],
        )
        self.assertIn("Area 10", stores[-1].availability)
        self.assertEqual(resolve_location_special_vendors(6), ())

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
