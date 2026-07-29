from __future__ import annotations

import unittest

from romwiki.engines.gen5.bw.static_encounters import parse_static_encounters


def _word(value: int) -> bytes:
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


class Gen5StaticEncounterTests(unittest.TestCase):
    def test_decodes_real_static_encounters(self) -> None:
        # Real Black ROM facts: script file 304 offset 0x121 holds Pansage
        # (species 511) at level 10 (offset 0x29D); file 526 offset 0x758
        # holds the free tutorial Magikarp (species 129) at level 5.
        files = {
            304: _padded(0x2A0, {0x121: _word(511), 0x29D: bytes((10,))}),
            526: _padded(0x760, {0x758: _word(129), 0x75C: bytes((5,))}),
            776: _padded(0x90, {0x85: _word(636)}),
        }
        entries = [
            {"species": (304, 0x121), "level": (304, 0x29D)},
            {"species": (526, 0x758), "level": (526, 0x75C)},
            {"species": (776, 0x85), "level": None},
        ]

        encounters = parse_static_encounters(
            files.__getitem__,
            entries,
            egg_indices=frozenset({2}),
            archive_path="a/0/5/7",
        )

        self.assertEqual(len(encounters), 3)
        pansage, magikarp, larvesta = encounters
        self.assertEqual(pansage.species_id, 511)
        self.assertEqual(pansage.level, 10)
        self.assertFalse(pansage.is_egg)
        self.assertEqual(magikarp.species_id, 129)
        self.assertEqual(magikarp.level, 5)
        self.assertEqual(larvesta.species_id, 636)
        self.assertIsNone(larvesta.level)
        self.assertTrue(larvesta.is_egg)
        self.assertEqual(pansage.provenance.archive, "a/0/5/7")
        self.assertEqual(pansage.provenance.member, 0)

    def test_egg_indices_apply_only_to_the_named_encounter(self) -> None:
        files = {1: _padded(4, {0: _word(1)})}
        entries = [{"species": (1, 0), "level": None}]

        encounters = parse_static_encounters(
            files.__getitem__, entries, egg_indices=frozenset(), archive_path="scripts"
        )

        self.assertFalse(encounters[0].is_egg)


def _padded(length: int, values: dict[int, bytes]) -> bytes:
    data = bytearray(length)
    for offset, chunk in values.items():
        data[offset : offset + len(chunk)] = chunk
    return bytes(data)


if __name__ == "__main__":
    unittest.main()
