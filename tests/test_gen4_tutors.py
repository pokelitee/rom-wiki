from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt.tutors import (
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)
from romwiki.errors import InvalidRomError


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
        self.assertEqual([record.personal_member for record in compatibility], [1, 2, 5])
        self.assertEqual(compatibility[0].tutor_ids, (1,))
        self.assertEqual(compatibility[1].tutor_ids, ())

    def test_rejects_bad_tutor_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(b"short", tutor_count=1)
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(
                struct.pack("<H4B2sI", 1, 0, 0, 0, 0, b"xx", 0), tutor_count=1
            )
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
