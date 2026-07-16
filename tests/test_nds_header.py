from __future__ import annotations

import struct
import unittest

from romwiki.errors import InvalidRomError
from romwiki.platforms.nds.header import NintendoDSHeader


def make_header() -> bytes:
    data = bytearray(0x200)
    data[0:12] = b"POKEMON PL\0\0"
    data[0x0C:0x10] = b"CPUE"
    data[0x10:0x12] = b"01"
    data[0x14] = 10
    data[0x1E] = 1
    struct.pack_into("<I", data, 0x20, 0x4000)
    struct.pack_into("<I", data, 0x2C, 0x100)
    struct.pack_into("<I", data, 0x30, 0x5000)
    struct.pack_into("<I", data, 0x3C, 0x100)
    struct.pack_into("<I", data, 0x40, 0x6000)
    struct.pack_into("<I", data, 0x44, 0x100)
    struct.pack_into("<I", data, 0x48, 0x7000)
    struct.pack_into("<I", data, 0x4C, 0x40)
    struct.pack_into("<I", data, 0x84, 0x4000)
    return bytes(data)


class NintendoDSHeaderTests(unittest.TestCase):
    def test_parses_identity_and_filesystem_count(self) -> None:
        header = NintendoDSHeader.from_bytes(make_header())

        self.assertEqual(header.title, "POKEMON PL")
        self.assertEqual(header.game_code, "CPUE")
        self.assertEqual(header.rom_version, 1)
        self.assertEqual(header.filesystem_file_count, 8)
        self.assertEqual(header.declared_capacity_bytes, 128 * 1024 * 1024)

    def test_rejects_short_header(self) -> None:
        with self.assertRaises(InvalidRomError):
            NintendoDSHeader.from_bytes(b"CPUE")


if __name__ == "__main__":
    unittest.main()

