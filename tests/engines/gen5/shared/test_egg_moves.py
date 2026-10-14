from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.egg_moves import parse_egg_move_set
from romwiki.util.errors import InvalidRomError


class Gen5EggMoveTests(unittest.TestCase):
    def test_decodes_a_species_egg_move_set(self) -> None:
        # Real Bulbasaur record: count word (14) followed by 14 move IDs.
        move_ids = (
            130,
            204,
            80,
            345,
            320,
            174,
            275,
            267,
            389,
            437,
            438,
            124,
            203,
            202,
        )
        data = struct.pack(f"<H{len(move_ids)}H", len(move_ids), *move_ids)

        egg_move_set = parse_egg_move_set(data, species_id=1, archive_path="egg.narc")

        self.assertEqual(egg_move_set.move_ids, move_ids)
        self.assertEqual(egg_move_set.provenance.member, 1)
        self.assertEqual(egg_move_set.provenance.archive, "egg.narc")

    def test_accepts_a_species_with_no_egg_moves(self) -> None:
        egg_move_set = parse_egg_move_set(
            struct.pack("<H", 0), species_id=25, archive_path="egg.narc"
        )
        self.assertEqual(egg_move_set.move_ids, ())

    def test_accepts_the_empty_placeholder_record(self) -> None:
        # Member 0 of the real archive is a zero-length unused placeholder.
        egg_move_set = parse_egg_move_set(b"", species_id=0, archive_path="egg.narc")
        self.assertEqual(egg_move_set.move_ids, ())

    def test_rejects_a_count_mismatched_with_the_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_egg_move_set(
                struct.pack("<HH", 2, 33), species_id=1, archive_path="egg.narc"
            )

    def test_rejects_an_unaligned_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_egg_move_set(b"\0\0\0", species_id=1, archive_path="egg.narc")

    def test_rejects_an_invalid_move_id(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_egg_move_set(
                struct.pack("<HH", 1, 0), species_id=1, archive_path="egg.narc"
            )


if __name__ == "__main__":
    unittest.main()
