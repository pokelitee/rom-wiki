from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.tutors import (
    TUTOR_COUNT,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)
from romwiki.util.errors import InvalidRomError


class HgssTutorTests(unittest.TestCase):
    def test_decodes_bp_costs_and_locations(self) -> None:
        records = [(291, 40)] * (TUTOR_COUNT - 1) + [(29, 3 << 8)]
        tutors = parse_tutor_move_table(
            b"".join(struct.pack("<HH", *record) for record in records)
        )

        self.assertEqual(tutors[0].move_id, 291)
        self.assertEqual(tutors[0].battle_point_cost, 40)
        self.assertEqual(tutors[0].location_id, 0)
        self.assertEqual(tutors[-1].move_id, 29)
        self.assertEqual(tutors[-1].battle_point_cost, 0)
        self.assertEqual(tutors[-1].location_id, 3)

    def test_rejects_invalid_ilex_forest_record(self) -> None:
        records = [(291, 40)] * TUTOR_COUNT
        records[-1] = (29, (3 << 8) | 32)

        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(
                b"".join(struct.pack("<HH", *record) for record in records)
            )

    def test_decodes_compatibility_bits_and_form_members(self) -> None:
        masks = [0] * 3
        masks[0] = (1 << 0) | (1 << 51)
        records = parse_tutor_compatibility_table(
            b"".join(mask.to_bytes(8, "little") for mask in masks),
            base_species_count=2,
            form_member_start=4,
            form_count=1,
        )

        self.assertEqual(records[0].personal_member, 1)
        self.assertEqual(records[0].tutor_ids, (1, 52))
        self.assertEqual(records[2].personal_member, 4)

    def test_rejects_unknown_compatibility_bits(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_compatibility_table(
                (1 << 52).to_bytes(8, "little"),
                base_species_count=1,
                form_member_start=2,
                form_count=0,
            )
