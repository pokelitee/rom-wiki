from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss import parse_encounter_record
from romwiki.util.errors import InvalidRomError


class HGSSEncounterTests(unittest.TestCase):
    def test_decodes_time_periods_water_and_special_species(self) -> None:
        data = bytearray(196)
        data[:6] = bytes((30, 10, 5, 20, 25, 30))
        data[8:20] = bytes(range(5, 17))
        for offset, first_species in ((20, 1), (44, 101), (68, 201)):
            struct.pack_into(
                "<12H", data, offset, *range(first_species, first_species + 12)
            )
        struct.pack_into("<4H", data, 92, 252, 253, 254, 255)
        _write_method(data, 100, 5, species=60)
        _write_method(data, 120, 2, species=70)
        _write_method(data, 128, 5, species=80)
        _write_method(data, 148, 5, species=90)
        _write_method(data, 168, 5, species=100)
        struct.pack_into("<4H", data, 188, 120, 121, 122, 123)

        record = parse_encounter_record(bytes(data), area_id=4, archive_path="wild")

        self.assertEqual(record.walking_variants["morning"][0].species_id, 1)
        self.assertEqual(record.walking_variants["day"][0].species_id, 101)
        self.assertEqual(record.walking_variants["night"][0].species_id, 201)
        self.assertEqual(record.rock_smash.slots[0].species_id, 70)
        self.assertEqual(record.swarm_species_ids, (120, 121))
        self.assertEqual(record.night_fishing_species_id, 122)
        self.assertEqual(record.fishing_swarm_species_id, 123)

    def test_accepts_verified_hack_shape_without_final_replacements(self) -> None:
        record = parse_encounter_record(bytes(192), area_id=0, archive_path="wild")

        self.assertIsNone(record.night_fishing_species_id)
        self.assertIsNone(record.fishing_swarm_species_id)

    def test_rejects_other_sizes(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_encounter_record(bytes(191), area_id=0, archive_path="wild")


def _write_method(data: bytearray, offset: int, count: int, *, species: int) -> None:
    for index in range(count):
        struct.pack_into("<BBH", data, offset + index * 4, 10, 12, species + index)


if __name__ == "__main__":
    unittest.main()
