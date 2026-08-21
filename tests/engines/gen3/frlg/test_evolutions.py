from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.frlg.evolutions import parse_evolution_record
from romwiki.util.errors import InvalidRomError


def _slot(data: bytearray, index: int, method: int, param: int, target: int) -> None:
    struct.pack_into("<HHH", data, index * 8, method, param, target)


class ParseEvolutionRecordTests(unittest.TestCase):
    def test_decodes_a_single_level_up_evolution(self) -> None:
        # Real Bulbasaur record: level 16 -> Ivysaur.
        data = bytearray(40)
        _slot(data, 0, 4, 16, 2)

        result = parse_evolution_record(
            bytes(data), species_id=1, archive_path="offset:0x0"
        )

        self.assertEqual(len(result.evolutions), 1)
        self.assertEqual(result.evolutions[0].method_id, 4)
        self.assertEqual(result.evolutions[0].parameter, 16)
        self.assertEqual(result.evolutions[0].target_species_id, 2)
        self.assertEqual(result.provenance.member, 1)

    def test_decodes_all_five_slots(self) -> None:
        # Real Eevee record: three item evolutions plus friendship-day/night.
        data = bytearray(40)
        _slot(data, 0, 7, 96, 135)
        _slot(data, 1, 7, 97, 134)
        _slot(data, 2, 7, 95, 136)
        _slot(data, 3, 2, 0, 196)
        _slot(data, 4, 3, 0, 197)

        result = parse_evolution_record(
            bytes(data), species_id=133, archive_path="offset:0x0"
        )

        self.assertEqual(len(result.evolutions), 5)
        self.assertEqual(result.evolutions[4].method_id, 3)
        self.assertEqual(result.evolutions[4].target_species_id, 197)

    def test_accepts_an_all_empty_record(self) -> None:
        result = parse_evolution_record(
            bytes(40), species_id=0, archive_path="offset:0x0"
        )
        self.assertEqual(result.evolutions, ())

    def test_ignores_unused_padding_bytes(self) -> None:
        data = bytearray(40)
        _slot(data, 0, 4, 16, 2)
        struct.pack_into("<H", data, 6, 0xFFFF)  # padding, must be ignored

        result = parse_evolution_record(
            bytes(data), species_id=1, archive_path="offset:0x0"
        )

        self.assertEqual(len(result.evolutions), 1)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(b"short", species_id=1, archive_path="offset:0x0")

    def test_rejects_an_incomplete_slot(self) -> None:
        data = bytearray(40)
        _slot(data, 0, 4, 16, 0)
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(bytes(data), species_id=1, archive_path="offset:0x0")


if __name__ == "__main__":
    unittest.main()
