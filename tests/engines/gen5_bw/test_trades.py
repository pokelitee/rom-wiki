from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.trades import parse_npc_trade_record
from romwiki.util.errors import InvalidRomError


def _trade_record(
    *,
    offered_species_id: int,
    offered_forme_id: int = 0,
    ivs: tuple[int, int, int, int, int, int],
    ot_id: int,
    held_item_id: int,
    requested_species_id: int,
) -> bytes:
    record = bytearray(108)
    struct.pack_into("<I", record, 4, offered_species_id)
    struct.pack_into("<I", record, 8, offered_forme_id)
    struct.pack_into("<6I", record, 0x10, *ivs)
    struct.pack_into("<H", record, 0x34, ot_id)
    struct.pack_into("<I", record, 0x4C, held_item_id)
    struct.pack_into("<I", record, 0x5C, requested_species_id)
    return bytes(record)


class Gen5NpcTradeTests(unittest.TestCase):
    def test_decodes_a_real_trade(self) -> None:
        # Real Black ROM trade 6: "Eeks" the Rotom (species 479) for a
        # Ditto (species 132), from OT "Lillian" (ID 54673), no held item.
        data = _trade_record(
            offered_species_id=479,
            ivs=(20, 20, 20, 20, 20, 31),
            ot_id=54673,
            held_item_id=0,
            requested_species_id=132,
        )

        trade = parse_npc_trade_record(
            data,
            trade_id=6,
            nickname="Eeks",
            ot_name="Lillian",
            archive_path="trades.narc",
        )

        self.assertEqual(trade.offered_species_id, 479)
        self.assertEqual(trade.requested_species_id, 132)
        self.assertEqual(trade.ot_id, 54673)
        self.assertEqual(trade.nickname, "Eeks")
        self.assertEqual(trade.ot_name, "Lillian")
        self.assertIsNone(trade.held_item_id)
        self.assertEqual(trade.ivs, (20, 20, 20, 20, 20, 31))
        self.assertEqual(trade.provenance.archive, "trades.narc")
        self.assertEqual(trade.provenance.member, 6)

    def test_decodes_a_trade_with_a_held_item(self) -> None:
        # Real Black ROM trade 5: "Gorge" the Munchlax holding a Leftovers
        # (item 234), requesting a Cinccino (species 573).
        data = _trade_record(
            offered_species_id=446,
            ivs=(31, 20, 20, 20, 20, 20),
            ot_id=40217,
            held_item_id=234,
            requested_species_id=573,
        )

        trade = parse_npc_trade_record(
            data,
            trade_id=5,
            nickname="Gorge",
            ot_name="Ander",
            archive_path="trades.narc",
        )

        self.assertEqual(trade.held_item_id, 234)

    def test_decodes_a_forme_id(self) -> None:
        # Real Black ROM: trade 2 (active, red-striped Basculin) has
        # offered_forme_id 0; the inactive White-counterpart trade 3
        # (blue-striped) has 1 at the same offset -- the only byte
        # difference between the two records besides bookkeeping fields.
        data = _trade_record(
            offered_species_id=550,
            offered_forme_id=1,
            ivs=(20, 31, 20, 20, 20, 20),
            ot_id=27646,
            held_item_id=0,
            requested_species_id=572,
        )

        trade = parse_npc_trade_record(
            data,
            trade_id=3,
            nickname="Blueeye",
            ot_name="Kyle",
            archive_path="trades.narc",
        )

        self.assertEqual(trade.offered_forme_id, 1)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_npc_trade_record(
                b"short",
                trade_id=0,
                nickname="x",
                ot_name="y",
                archive_path="trades.narc",
            )


if __name__ == "__main__":
    unittest.main()
