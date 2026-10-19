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


# Each table index mapped to a distinct synthetic header ID.
_LOCATION_IDS = {table_index: 100 + table_index for table_index in range(15)}


class ParseTutorMoveTableTests(unittest.TestCase):
    def test_decodes_every_located_tutor_in_table_order(self) -> None:
        records = parse_tutor_move_table(_move_table(), location_ids=_LOCATION_IDS)

        self.assertEqual(len(records), 15)
        self.assertEqual(
            [(r.tutor_id, r.move_id, r.location_id) for r in records[:3]],
            [(1, 5, 100), (2, 14, 101), (3, 25, 102)],
        )
        self.assertEqual((records[-1].tutor_id, records[-1].move_id), (15, 164))
        self.assertEqual(records[0].shard_costs.red, 0)
        self.assertEqual(records[0].table_index, 0)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_move_table(b"short", location_ids=_LOCATION_IDS)


class ParseTutorCompatibilityTests(unittest.TestCase):
    def test_numbers_each_compatible_tutor_from_its_table_index(self) -> None:
        # Real Bulbasaur mask: Swords Dance/Body Slam/Double-Edge/Mimic/
        # Substitute.
        bits = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 7) | (1 << 14)
        data = struct.pack("<H", bits)

        record = parse_tutor_compatibility(data, species_id=1, table_index=0)

        assert record is not None
        self.assertEqual(record.personal_member, 1)
        self.assertEqual(record.tutor_ids, (2, 4, 5, 8, 15))

    def test_returns_none_without_a_compatible_tutor(self) -> None:
        data = struct.pack("<H", 0)

        self.assertIsNone(parse_tutor_compatibility(data, species_id=1, table_index=0))

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tutor_compatibility(b"x", species_id=1, table_index=0)


if __name__ == "__main__":
    unittest.main()
