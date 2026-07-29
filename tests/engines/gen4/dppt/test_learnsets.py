from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt.learnsets import parse_level_up_learnset
from romwiki.util.errors import InvalidRomError


class Gen4LearnsetTests(unittest.TestCase):
    def test_decodes_packed_level_and_move_entries(self) -> None:
        values = ((1 << 9) | 33, (1 << 9) | 45, (5 << 9) | 73, 0xFFFF)
        data = struct.pack("<4H", *values)

        learnset = parse_level_up_learnset(
            data, species_id=1, archive_path="wotbl.narc"
        )

        self.assertEqual(
            [(entry.level, entry.move_id) for entry in learnset.moves],
            [(1, 33), (1, 45), (5, 73)],
        )
        self.assertEqual(learnset.provenance.member, 1)

    def test_accepts_alignment_padding_after_terminator(self) -> None:
        learnset = parse_level_up_learnset(
            struct.pack("<2H", 0xFFFF, 0),
            species_id=0,
            archive_path="wotbl.narc",
        )
        self.assertEqual(learnset.moves, ())

    def test_rejects_missing_terminator_or_invalid_trailing_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_level_up_learnset(
                struct.pack("<H", 33), species_id=1, archive_path="wotbl.narc"
            )
        with self.assertRaises(InvalidRomError):
            parse_level_up_learnset(
                struct.pack("<3H", 33, 0xFFFF, 1),
                species_id=1,
                archive_path="wotbl.narc",
            )


if __name__ == "__main__":
    unittest.main()
