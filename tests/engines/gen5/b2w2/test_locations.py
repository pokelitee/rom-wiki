from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.locations import (
    NPC_TRADE_INTERACTION_BY_ID,
    NPC_TRADE_TEXT_MEMBER_BY_ID,
    parse_map_header_table,
    parse_wild_map_names,
    resolve_common_script_member,
)
from romwiki.engines.registry import get_engine

_MAP_NAMES = ("Route 1", "Route 2")


def _map_header(*, name_index: int, wild_set: int) -> bytes:
    record = bytearray(48)
    record[26] = name_index
    struct.pack_into("<H", record, 20, wild_set)
    return bytes(record)


class Gen5B2W2LocationsTests(unittest.TestCase):
    def test_resolves_common_fossil_script_and_fixed_trade_text_members(self) -> None:
        self.assertEqual(resolve_common_script_member(10445, member_count=1300), 1253)
        self.assertEqual(NPC_TRADE_INTERACTION_BY_ID[0], "xtransceiver")
        self.assertEqual(NPC_TRADE_INTERACTION_BY_ID[23], "xtransceiver")
        self.assertNotIn(24, NPC_TRADE_INTERACTION_BY_ID)
        self.assertEqual(NPC_TRADE_TEXT_MEMBER_BY_ID[24], 529)
        self.assertEqual(NPC_TRADE_TEXT_MEMBER_BY_ID[30], 628)

    def test_engine_uses_the_b2w2_location_decoder(self) -> None:
        adapter = get_engine("gen5_b2w2")
        locations = adapter.locations

        self.assertIs(locations.parse_map_header_table, parse_map_header_table)
        self.assertTrue(callable(locations.parse_english_message_archive))
        self.assertEqual(
            adapter.trades.NPC_TRADE_INTERACTION_BY_ID[0], "xtransceiver"
        )
        self.assertTrue(callable(adapter.trades.parse_npc_trade_record))
        self.assertFalse(
            hasattr(get_engine("gen5_bw").trades, "NPC_TRADE_INTERACTION_BY_ID")
        )

    def test_extracts_the_encounter_index_from_the_low_twelve_bits(self) -> None:
        data = _map_header(name_index=0, wild_set=0x4052) + _map_header(
            name_index=1, wild_set=0xC029
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertEqual(
            [header.encounter_map_index for header in headers],
            [82, 41],
        )

    def test_treats_flagged_null_encounter_indexes_as_absent(self) -> None:
        data = b"".join(
            _map_header(name_index=0, wild_set=value)
            for value in (0x0FFF, 0x1FFF, 0x5FFF, 0xBFFF, 0xDFFF, 0xFFFF)
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertTrue(all(header.encounter_map_index is None for header in headers))
        self.assertEqual(parse_wild_map_names(data, map_names=_MAP_NAMES), {})


if __name__ == "__main__":
    unittest.main()
