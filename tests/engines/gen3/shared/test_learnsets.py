from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.learnsets import parse_level_up_learnset
from romwiki.util.errors import InvalidRomError


def _entry(level: int, move_id: int) -> int:
    return level << 9 | move_id


class ParseLevelUpLearnsetTests(unittest.TestCase):
    def test_decodes_moves_up_to_the_terminator(self) -> None:
        data = struct.pack(
            "<5H", _entry(1, 33), _entry(4, 45), _entry(100, 354), 0xFFFF, 0x1234
        )

        learnset = parse_level_up_learnset(
            data, species_id=1, archive_path="offset:0x25d7b4"
        )

        self.assertEqual(
            [(move.level, move.move_id) for move in learnset.moves],
            [(1, 33), (4, 45), (100, 354)],
        )
        self.assertEqual(learnset.species_id, 1)
        self.assertEqual(learnset.provenance.archive, "offset:0x25d7b4")
        self.assertEqual(learnset.provenance.member, 1)

    def test_ignores_a_trailing_odd_byte_after_the_terminator(self) -> None:
        data = struct.pack("<2H", _entry(1, 33), 0xFFFF) + b"\x00"

        learnset = parse_level_up_learnset(data, species_id=1, archive_path="x")

        self.assertEqual(len(learnset.moves), 1)

    def test_rejects_a_learnset_without_a_terminator(self) -> None:
        data = struct.pack("<2H", _entry(1, 33), _entry(4, 45))

        with self.assertRaisesRegex(InvalidRomError, "no terminator"):
            parse_level_up_learnset(data, species_id=7, archive_path="x")


if __name__ == "__main__":
    unittest.main()
