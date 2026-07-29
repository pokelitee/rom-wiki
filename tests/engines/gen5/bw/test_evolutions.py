from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.bw.evolutions import parse_evolution_record
from romwiki.util.errors import InvalidRomError


class Gen5EvolutionTests(unittest.TestCase):
    def test_decodes_ordered_evolution_slots(self) -> None:
        # Real Tyrogue record: attack-greater -> Hitmonlee, defense-greater ->
        # Hitmonchan, atk-def-same -> Hitmontop, all at level 20.
        data = bytearray(42)
        struct.pack_into("<3H", data, 0, 11, 20, 107)
        struct.pack_into("<3H", data, 6, 9, 20, 106)
        struct.pack_into("<3H", data, 12, 10, 20, 237)

        result = parse_evolution_record(
            bytes(data), species_id=236, archive_path="evo.narc"
        )

        self.assertEqual(len(result.evolutions), 3)
        self.assertEqual(result.evolutions[0].method_id, 11)
        self.assertEqual(result.evolutions[0].parameter, 20)
        self.assertEqual(result.evolutions[0].target_species_id, 107)
        self.assertEqual(result.evolutions[2].target_species_id, 237)
        self.assertEqual(result.provenance.member, 236)

    def test_accepts_an_all_empty_record(self) -> None:
        result = parse_evolution_record(
            bytes(42), species_id=0, archive_path="evo.narc"
        )
        self.assertEqual(result.evolutions, ())

    def test_ignores_a_disabled_slot_with_stale_operands(self) -> None:
        # Blaze Black/Volt White disable Feebas's former evolution by clearing
        # only its method, leaving the parameter and target operands in place.
        data = bytearray(42)
        struct.pack_into("<3H", data, 0, 0, 170, 350)
        struct.pack_into("<3H", data, 6, 8, 537, 350)

        result = parse_evolution_record(
            bytes(data), species_id=349, archive_path="evo.narc"
        )

        self.assertEqual(len(result.evolutions), 1)
        self.assertEqual(result.evolutions[0].method_id, 8)
        self.assertEqual(result.evolutions[0].parameter, 537)
        self.assertEqual(result.evolutions[0].target_species_id, 350)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(b"short", species_id=1, archive_path="evo.narc")

    def test_rejects_incomplete_or_noncontiguous_slots(self) -> None:
        incomplete = bytearray(42)
        struct.pack_into("<3H", incomplete, 0, 4, 16, 0)
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(
                bytes(incomplete), species_id=1, archive_path="evo.narc"
            )

        noncontiguous = bytearray(42)
        struct.pack_into("<3H", noncontiguous, 6, 4, 16, 2)
        with self.assertRaises(InvalidRomError):
            parse_evolution_record(
                bytes(noncontiguous), species_id=1, archive_path="evo.narc"
            )


if __name__ == "__main__":
    unittest.main()
