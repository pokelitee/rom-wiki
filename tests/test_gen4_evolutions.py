from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt.evolutions import parse_evolution_record
from romwiki.errors import InvalidRomError


class Gen4EvolutionTests(unittest.TestCase):
    def test_decodes_ordered_evolution_slots(self) -> None:
        data = bytearray(44)
        struct.pack_into("<3H", data, 0, 7, 83, 26)
        struct.pack_into("<3H", data, 6, 4, 32, 100)

        result = parse_evolution_record(
            bytes(data), species_id=25, archive_path="evo.narc"
        )

        self.assertEqual(len(result.evolutions), 2)
        self.assertEqual(result.evolutions[0].method_id, 7)
        self.assertEqual(result.evolutions[0].parameter, 83)
        self.assertEqual(result.evolutions[0].target_species_id, 26)
        self.assertEqual(result.evolutions[1].method_id, 4)
        self.assertEqual(result.provenance.member, 25)

    def test_rejects_wrong_size_and_nonzero_padding(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(b"short", species_id=1, archive_path="evo.narc")
        data = bytearray(44)
        data[42] = 1
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(bytes(data), species_id=1, archive_path="evo.narc")

    def test_rejects_incomplete_or_noncontiguous_slots(self) -> None:
        incomplete = bytearray(44)
        struct.pack_into("<3H", incomplete, 0, 0, 16, 2)
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(
                bytes(incomplete), species_id=1, archive_path="evo.narc"
            )

        noncontiguous = bytearray(44)
        struct.pack_into("<3H", noncontiguous, 6, 4, 16, 2)
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(
                bytes(noncontiguous), species_id=1, archive_path="evo.narc"
            )


if __name__ == "__main__":
    unittest.main()
