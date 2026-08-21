from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.frlg.tutors import (
    parse_tutor_compatibility,
    parse_tutor_move_table,
)
from romwiki.util.errors import InvalidRomError


def _move_table() -> bytes:
    # Real sTutorMoves order (verified against the ROM): Mega Punch/Swords
    # Dance/Mega Kick/Body Slam/Double-Edge/Counter/Seismic Toss/Mimic/
    # Metronome/Softboiled/Dream Eater/Thunder Wave/Explosion/Rock Slide/
    # Substitute.
    ids = [5, 14, 25, 34, 38, 68, 69, 102, 118, 135, 138, 86, 153, 157, 164]
    return struct.pack("<15H", *ids)


class ParseTutorMoveTableTests(unittest.TestCase):
    def test_decodes_only_the_four_located_tutors(self) -> None:
        records = parse_tutor_move_table(_move_table())

        self.assertEqual(len(records), 4)
        self.assertEqual(
            [(r.tutor_id, r.move_id, r.location_id) for r in records],
            [(1, 5, 15), (2, 25, 15), (3, 68, 30), (4, 164, 7)],
        )
        self.assertEqual(records[0].shard_costs.red, 0)
        self.assertEqual(records[0].table_index, 0)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(b"short")


class ParseTutorCompatibilityTests(unittest.TestCase):
    def test_keeps_only_the_four_exposed_tutor_bits(self) -> None:
        # Real Bulbasaur mask: Swords Dance/Body Slam/Double-Edge/Mimic/
        # Substitute -- only Substitute (table index 14) is one of the 4
        # exposed tutors.
        bits = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 7) | (1 << 14)
        data = struct.pack("<H", bits)

        record = parse_tutor_compatibility(data, species_id=1, table_index=0)

        assert record is not None
        self.assertEqual(record.personal_member, 1)
        self.assertEqual(record.tutor_ids, (4,))

    def test_returns_none_when_no_exposed_tutor_matches(self) -> None:
        bits = 1 << 1  # Swords Dance only, not one of the 4 exposed tutors
        data = struct.pack("<H", bits)

        self.assertIsNone(parse_tutor_compatibility(data, species_id=1, table_index=0))

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_compatibility(b"x", species_id=1, table_index=0)


if __name__ == "__main__":
    unittest.main()
