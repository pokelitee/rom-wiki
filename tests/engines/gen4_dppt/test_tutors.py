from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt.tutors import (
    parse_special_tutor_move,
    parse_special_tutor_species,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)
from romwiki.util.errors import InvalidRomError


class Gen4TutorTests(unittest.TestCase):
    def test_decodes_move_cost_location_and_compatibility(self) -> None:
        tutors = parse_tutor_move_table(
            struct.pack("<H4B2xI", 291, 2, 4, 2, 0, 1), tutor_count=1
        )
        compatibility = parse_tutor_compatibility_table(
            b"\x01\0\0\0\0" + b"\0" * 5 + b"\x01\0\0\0\0",
            tutor_count=1,
            base_species_count=2,
            form_member_start=5,
            form_count=1,
        )

        self.assertEqual(tutors[0].move_id, 291)
        self.assertEqual(tutors[0].shard_costs.red, 2)
        self.assertEqual(tutors[0].shard_costs.blue, 4)
        self.assertEqual(tutors[0].location_id, 1)
        self.assertEqual(
            [record.personal_member for record in compatibility], [1, 2, 5]
        )
        self.assertEqual(compatibility[0].tutor_ids, (1,))
        self.assertEqual(compatibility[1].tutor_ids, ())

    def test_rejects_bad_tutor_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(b"short", tutor_count=1)
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(
                struct.pack("<H4B2sI", 1, 0, 0, 0, 0, b"xx", 0), tutor_count=1
            )

    def test_decodes_scripted_tutor_assignment_and_species(self) -> None:
        data = bytearray(64)
        struct.pack_into("<HHHH", data, 4, 0x28, 0x8003, 307, 0x16)
        cursor = 16
        for species_id in (6, 157):
            struct.pack_into(
                "<HHHHBi", data, cursor, 0x11, 0x8001, species_id, 0x1C, 1, 0
            )
            cursor += 13

        species = parse_special_tutor_species(
            bytes(data), comparison_offset=16, species_count=2
        )
        tutor = parse_special_tutor_move(
            bytes(data),
            tutor_id=40,
            script_member=493,
            command_offset=4,
            map_header_id=502,
            location_name="Route 228",
            eligibility_kind="species",
            eligibility_value=species,
            minimum_friendship=255,
        )

        self.assertEqual(species, (6, 157))
        self.assertEqual(tutor.move_id, 307)
        self.assertEqual(tutor.command_offset, 4)
        with self.assertRaises(InvalidRomError):
            parse_tutor_compatibility_table(
                b"\x02\0\0\0\0",
                tutor_count=1,
                base_species_count=1,
                form_member_start=2,
                form_count=0,
            )


if __name__ == "__main__":
    unittest.main()
