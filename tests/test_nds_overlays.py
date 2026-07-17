from __future__ import annotations

import struct
import unittest

from romwiki.errors import InvalidRomError
from romwiki.platforms.nds.overlays import parse_overlay_table


class NintendoDSOverlayTests(unittest.TestCase):
    def test_parses_overlay_records(self) -> None:
        overlays = parse_overlay_table(struct.pack("<8I", 5, 100, 200, 30, 150, 160, 9, 0))

        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0].id, 5)
        self.assertEqual(overlays[0].file_id, 9)
        self.assertEqual(overlays[0].ram_size, 200)

    def test_rejects_invalid_size_and_duplicate_ids(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_overlay_table(b"short")
        duplicate = struct.pack("<16I", *(tuple(range(8)) + tuple(range(8))))
        with self.assertRaises(InvalidRomError):
            parse_overlay_table(duplicate)


if __name__ == "__main__":
    unittest.main()
