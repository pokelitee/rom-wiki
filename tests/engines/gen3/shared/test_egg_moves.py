from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.egg_moves import parse_egg_move_table
from romwiki.util.errors import InvalidRomError


class ParseEggMoveTableTests(unittest.TestCase):
    def test_decodes_species_markers_and_move_lists(self) -> None:
        data = b"pad!" + struct.pack(
            "<8H", 20001, 113, 130, 20004, 187, 246, 157, 0xFFFF
        )

        records = parse_egg_move_table(data, table_offset=4)

        self.assertEqual([record.species_id for record in records], [1, 4])
        self.assertEqual(records[0].move_ids, (113, 130))
        self.assertEqual(records[1].move_ids, (187, 246, 157))
        self.assertEqual(records[1].overlay_offset, 10)
        self.assertEqual(records[0].table_index, 0)
        self.assertEqual(records[1].table_index, 1)

    def test_keeps_species_through_the_last_internal_species(self) -> None:
        data = struct.pack("<7H", 20001, 113, 20387, 187, 20411, 50, 0xFFFF)

        records = parse_egg_move_table(data)

        self.assertEqual([record.species_id for record in records], [1, 387, 411])
        self.assertEqual([record.table_index for record in records], [0, 1, 2])

    def test_rejects_invalid_or_unterminated_tables(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_egg_move_table(struct.pack("<3H", 20001, 113, 20001))
        with self.assertRaises(InvalidRomError):
            parse_egg_move_table(struct.pack("<2H", 20001, 468))
        with self.assertRaises(InvalidRomError):
            parse_egg_move_table(struct.pack("<2H", 20001, 0xFFFF))


if __name__ == "__main__":
    unittest.main()
