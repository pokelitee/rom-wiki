from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import parse_species_list


class Gen4BonusEncountersTests(unittest.TestCase):
    def test_parses_flat_u32_species_table(self) -> None:
        data = struct.pack("<6I", 415, 265, 412, 420, 190, 190)

        species = parse_species_list(data)

        self.assertEqual(species, (415, 265, 412, 420, 190, 190))

    def test_parses_single_entry_table(self) -> None:
        self.assertEqual(parse_species_list(struct.pack("<I", 446)), (446,))


if __name__ == "__main__":
    unittest.main()
