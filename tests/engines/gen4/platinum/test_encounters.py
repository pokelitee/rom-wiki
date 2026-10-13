from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import parse_encounter_record
from romwiki.util.errors import InvalidRomError


class Gen4EncounterTests(unittest.TestCase):
    def test_decodes_walking_special_and_water_encounters(self) -> None:
        data = bytearray(424)
        struct.pack_into("<I", data, 0, 30)
        struct.pack_into("<II", data, 4, 12, 25)
        struct.pack_into("<2I", data, 0x64, 81, 100)
        struct.pack_into("<4I", data, 0x7C, 123, 124, 125, 126)
        struct.pack_into("<2I", data, 0xA4, 127, 128)
        _write_water_method(data, 0xCC, rate=10, maximum=22, minimum=20, species=129)
        _write_water_method(data, 0x17C, rate=25, maximum=40, minimum=35, species=130)

        record = parse_encounter_record(
            bytes(data), area_id=7, archive_path="encounters.narc"
        )

        self.assertEqual(record.walking_rate, 30)
        self.assertEqual(record.walking_slots[0].level, 12)
        self.assertEqual(record.walking_slots[0].species_id, 25)
        self.assertEqual(record.swarm_species_ids, (81, 100))
        self.assertEqual(record.radar_species_ids[-1], 126)
        self.assertEqual(record.dual_slot_species_ids["ruby"], (127, 128))
        self.assertEqual(record.surf.slots[0].minimum_level, 20)
        self.assertEqual(record.surf.slots[0].maximum_level, 22)
        self.assertEqual(record.super_rod.rate, 25)
        self.assertEqual(record.provenance.member, 7)

    def test_accepts_vanilla_record_without_trailing_super_rod_table(self) -> None:
        record = parse_encounter_record(
            bytes(380), area_id=0, archive_path="encounters.narc"
        )

        self.assertEqual(record.super_rod.rate, 0)
        self.assertEqual(record.super_rod.slots, ())

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_encounter_record(
                bytes(379), area_id=0, archive_path="encounters.narc"
            )


def _write_water_method(
    data: bytearray,
    offset: int,
    *,
    rate: int,
    maximum: int,
    minimum: int,
    species: int,
) -> None:
    struct.pack_into("<I", data, offset, rate)
    struct.pack_into("<BBxxI", data, offset + 4, maximum, minimum, species)


if __name__ == "__main__":
    unittest.main()
