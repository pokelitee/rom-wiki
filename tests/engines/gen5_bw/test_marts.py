from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.marts import parse_shop_catalog


def _overlay_with_shop(offset: int, item_ids: tuple[int, ...]) -> bytes:
    data = bytearray(offset + len(item_ids) * 2)
    struct.pack_into(f"<{len(item_ids)}H", data, offset, *item_ids)
    return bytes(data)


class Gen5ShopCatalogTests(unittest.TestCase):
    def test_decodes_a_real_specialty_shop(self) -> None:
        # Real Black ROM shop 3, "Driftveil Herb Salesman": Heal Powder (36),
        # EnergyPowder (34), Energy Root (35), Revival Herb (37). Shop IDs 0-2
        # are dummy entries so shop 3 lands at its real ROM index.
        overlay_data = _overlay_with_shop(0x10, (36, 34, 35, 37))

        shops = parse_shop_catalog(
            overlay_data,
            shop_item_offsets=(0, 0, 0, 0x10),
            shop_item_sizes=(0, 0, 0, 4),
            tm_shop_ids=frozenset({1, 2}),
            regular_shop_ids=frozenset({0}),
            archive_path="overlay21",
        )

        self.assertEqual(len(shops), 1)
        shop = shops[0]
        self.assertEqual(shop.shop_id, 3)
        self.assertEqual(shop.name, "Driftveil Herb Salesman")
        self.assertTrue(shop.is_main_game)
        self.assertEqual(shop.item_ids, (36, 34, 35, 37))
        self.assertEqual(shop.provenance.archive, "overlay21")
        self.assertEqual(shop.provenance.member, 3)

    def test_skips_tm_and_regular_shops(self) -> None:
        overlay_data = _overlay_with_shop(0, (1, 2))

        shops = parse_shop_catalog(
            overlay_data,
            shop_item_offsets=(0, 0, 0),
            shop_item_sizes=(2, 2, 2),
            tm_shop_ids=frozenset({0}),
            regular_shop_ids=frozenset({1}),
            archive_path="overlay21",
        )

        self.assertEqual([shop.shop_id for shop in shops], [2])

    def test_marks_a_post_game_shop(self) -> None:
        # Real Black ROM shop 13, "Driftveil Incense Salesman", is not in
        # MAIN_GAME_SHOP_IDS.
        overlay_data = bytearray(20)
        shops = parse_shop_catalog(
            bytes(overlay_data),
            shop_item_offsets=tuple([0] * 14),
            shop_item_sizes=tuple([0] * 14),
            tm_shop_ids=frozenset(range(13)),
            regular_shop_ids=frozenset(),
            archive_path="overlay21",
        )

        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0].shop_id, 13)
        self.assertFalse(shops[0].is_main_game)


if __name__ == "__main__":
    unittest.main()
