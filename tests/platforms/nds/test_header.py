from __future__ import annotations

import unittest

from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_header


class NintendoDSHeaderTests(unittest.TestCase):
    def test_parses_identity_and_filesystem_count(self) -> None:
        header = NintendoDSHeader.from_bytes(make_header())

        self.assertEqual(header.title, "POKEMON PL")
        self.assertEqual(header.game_code, "CPUE")
        self.assertEqual(header.rom_version, 1)
        self.assertEqual(header.arm9_ram_address, 0x02000000)
        self.assertEqual(header.filesystem_file_count, 8)
        self.assertEqual(header.declared_capacity_bytes, 128 * 1024 * 1024)

    def test_rejects_short_header(self) -> None:
        with self.assertRaises(InvalidRomError):
            NintendoDSHeader.from_bytes(b"CPUE")


if __name__ == "__main__":
    unittest.main()
