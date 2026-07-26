from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.learnsets import parse_level_up_learnset
from romwiki.util.errors import InvalidRomError


class Gen5LearnsetTests(unittest.TestCase):
    def test_decodes_move_and_level_pairs(self) -> None:
        data = struct.pack("<8H", 33, 1, 45, 3, 73, 7, 0xFFFF, 0xFFFF)

        learnset = parse_level_up_learnset(
            data, species_id=1, archive_path="wotbl.narc"
        )

        self.assertEqual(
            [(entry.level, entry.move_id) for entry in learnset.moves],
            [(1, 33), (3, 45), (7, 73)],
        )
        self.assertEqual(learnset.provenance.member, 1)
        self.assertEqual(learnset.provenance.archive, "wotbl.narc")

    def test_accepts_an_immediately_terminated_empty_learnset(self) -> None:
        learnset = parse_level_up_learnset(
            struct.pack("<2H", 0xFFFF, 0xFFFF),
            species_id=0,
            archive_path="wotbl.narc",
        )
        self.assertEqual(learnset.moves, ())

    def test_ignores_disabled_move_zero_entries(self) -> None:
        learnset = parse_level_up_learnset(
            struct.pack("<6H", 0, 1, 33, 5, 0xFFFF, 0xFFFF),
            species_id=1,
            archive_path="wotbl.narc",
        )

        self.assertEqual(
            [(entry.level, entry.move_id) for entry in learnset.moves],
            [(5, 33)],
        )

    def test_rejects_missing_terminator(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_level_up_learnset(
                struct.pack("<2H", 33, 1), species_id=1, archive_path="wotbl.narc"
            )

    def test_rejects_an_unaligned_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_level_up_learnset(b"\0\0\0", species_id=1, archive_path="wotbl.narc")


if __name__ == "__main__":
    unittest.main()
