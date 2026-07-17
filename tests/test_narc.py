from __future__ import annotations

import struct
import unittest

from romwiki.errors import InvalidRomError
from romwiki.platforms.nds.narc import NarcArchive


def make_narc() -> bytes:
    raw_data = b"abc\0de"
    fat = struct.pack("<4sII", b"BTAF", 28, 2)
    fat += struct.pack("<IIII", 0, 3, 4, 6)
    fnt = struct.pack("<4sI", b"BTNF", 8)
    image = struct.pack("<4sI", b"GMIF", 8 + len(raw_data)) + raw_data
    file_size = 16 + len(fat) + len(fnt) + len(image)
    header = struct.pack("<4sHHIHH", b"NARC", 0xFFFE, 0x0100, file_size, 16, 3)
    return header + fat + fnt + image


class NarcArchiveTests(unittest.TestCase):
    def test_reads_members_using_allocation_offsets(self) -> None:
        archive = NarcArchive.from_bytes(make_narc())

        self.assertEqual(len(archive.members), 2)
        self.assertEqual(archive.read(0), b"abc")
        self.assertEqual(archive.read(1), b"de")

    def test_rejects_a_member_outside_the_data_block(self) -> None:
        data = bytearray(make_narc())
        struct.pack_into("<I", data, 24, 999)

        with self.assertRaises(InvalidRomError):
            NarcArchive.from_bytes(data)

    def test_can_read_available_part_of_an_explicitly_truncated_last_member(self) -> None:
        data = make_narc()[:-1]

        with self.assertRaises(InvalidRomError):
            NarcArchive.from_bytes(data)

        archive = NarcArchive.from_bytes(data, allow_truncated=True)
        self.assertEqual(archive.read(0), b"abc")
        self.assertEqual(archive.read(1), b"d")


if __name__ == "__main__":
    unittest.main()
