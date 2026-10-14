from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.items import parse_item_record
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
            bytes(data),
            item_id=17,
            data_archive_member=17,
            archive_path="itemdata.narc",
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

    def test_decodes_pocket_field_use_and_battle_use(self) -> None:
        # Real Black ROM Potion facts: Medicine pocket (1), field-use
        # "healing" (1), battle-use 2, no Natural Gift (sentinel 0x1F).
        data = bytearray(36)
        struct.pack_into("<H", data, 8, 0x1F | (1 << 7))
        data[10] = 1
        data[11] = 2

        item = parse_item_record(
            bytes(data), item_id=17, data_archive_member=17, archive_path="a/0/2/4"
        )

        self.assertEqual(item.field_pocket_id, 1)
        self.assertEqual(item.field_use_function_id, 1)
        self.assertEqual(item.battle_use_function_id, 2)
        self.assertEqual(item.natural_gift_type_id, 0x1F)

    def test_decodes_prevent_toss_selectable_and_battle_pocket_mask(self) -> None:
        # Real Black ROM facts: TM01 has prevent_toss set (you cannot toss a
        # TM in Black/White); Town Map has selectable set (it can be
        # registered to the quick-select button); Full Restore has battle
        # pocket bits 2 and 3 both set (0x0C) since it both restores HP and
        # cures status.
        data = bytearray(36)
        struct.pack_into("<H", data, 8, (1 << 5))
        item = parse_item_record(
            bytes(data), item_id=328, data_archive_member=328, archive_path="a/0/2/4"
        )
        self.assertTrue(item.prevent_toss)
        self.assertFalse(item.selectable)

        data = bytearray(36)
        struct.pack_into("<H", data, 8, (1 << 6))
        item = parse_item_record(
            bytes(data), item_id=442, data_archive_member=442, archive_path="a/0/2/4"
        )
        self.assertTrue(item.selectable)
        self.assertFalse(item.prevent_toss)

        data = bytearray(36)
        struct.pack_into("<H", data, 8, 0b1100 << 11)
        item = parse_item_record(
            bytes(data), item_id=23, data_archive_member=23, archive_path="a/0/2/4"
        )
        self.assertEqual(item.battle_pocket_mask, 0b1100)

    def test_decodes_a_real_berrys_natural_gift(self) -> None:
        # Real Black ROM Oran Berry: type 3 (poison), power 60.
        data = bytearray(36)
        data[7] = 60
        struct.pack_into("<H", data, 8, 3 | (3 << 7))

        item = parse_item_record(
            bytes(data), item_id=155, data_archive_member=155, archive_path="a/0/2/4"
        )

        self.assertEqual(item.natural_gift_power, 60)
        self.assertEqual(item.natural_gift_type_id, 3)
        self.assertEqual(item.field_pocket_id, 3)

    def test_decodes_full_restores_party_effects(self) -> None:
        # Real Black ROM Full Restore: cures all six status conditions and
        # restores to full HP (255 sentinel).
        data = bytearray(36)
        data[12] = 1  # party_use
        data[16] = 0x3F  # all six status-cure bits
        data[29] = 255  # hp_restored

        item = parse_item_record(
            bytes(data), item_id=23, data_archive_member=23, archive_path="a/0/2/4"
        )

        assert item.party_effects is not None
        self.assertTrue(item.party_use)
        self.assertTrue(item.party_effects.heal_sleep)
        self.assertTrue(item.party_effects.heal_poison)
        self.assertTrue(item.party_effects.heal_burn)
        self.assertTrue(item.party_effects.heal_freeze)
        self.assertTrue(item.party_effects.heal_paralysis)
        self.assertTrue(item.party_effects.heal_confusion)
        self.assertEqual(item.party_effects.hp_restored, 255)
        self.assertFalse(item.party_effects.revive)

    def test_disambiguates_revive_revive_all_and_level_up(self) -> None:
        # Real Black ROM facts: Revive=1 (revive only), Sacred Ash=3 (revive
        # + whole party), Rare Candy=5 (bit 0 shared, but redirected by bit
        # 2 into "level up" rather than "revive").
        def make(byte17: int) -> object:
            data = bytearray(36)
            data[12] = 1
            data[17] = byte17
            return parse_item_record(
                bytes(data), item_id=1, data_archive_member=1, archive_path="a/0/2/4"
            ).party_effects

        revive = make(1)
        sacred_ash = make(3)
        rare_candy = make(5)

        self.assertTrue(revive.revive)
        self.assertFalse(revive.revive_all)
        self.assertFalse(revive.level_up)

        self.assertTrue(sacred_ash.revive)
        self.assertTrue(sacred_ash.revive_all)
        self.assertFalse(sacred_ash.level_up)

        self.assertFalse(rare_candy.revive)
        self.assertFalse(rare_candy.revive_all)
        self.assertTrue(rare_candy.level_up)

    def test_decodes_ev_amounts_in_stat_order(self) -> None:
        # Real Black ROM HP Up: +10 HP EV only, nothing else.
        data = bytearray(36)
        data[12] = 1
        data[23] = 10

        item = parse_item_record(
            bytes(data), item_id=45, data_archive_member=45, archive_path="a/0/2/4"
        )

        assert item.party_effects is not None
        self.assertEqual(item.party_effects.hp_ev_amount, 10)
        self.assertEqual(item.party_effects.attack_ev_amount, 0)

    def test_decodes_negative_ev_amounts_from_ev_reducing_berries(self) -> None:
        # Real Black ROM Pomeg Berry: -10 HP EV only.
        data = bytearray(36)
        data[12] = 1
        struct.pack_into("<b", data, 23, -10)

        item = parse_item_record(
            bytes(data), item_id=155, data_archive_member=155, archive_path="a/0/2/4"
        )

        assert item.party_effects is not None
        self.assertEqual(item.party_effects.hp_ev_amount, -10)

    def test_no_party_effects_when_not_party_use(self) -> None:
        item = parse_item_record(
            bytes(36), item_id=1, data_archive_member=1, archive_path="a/0/2/4"
        )

        self.assertFalse(item.party_use)
        self.assertIsNone(item.party_effects)


if __name__ == "__main__":
    unittest.main()
