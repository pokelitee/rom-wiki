from __future__ import annotations

import unittest

from romwiki.platforms.gba.header import GbaHeader
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_gba_header


class GbaHeaderTests(unittest.TestCase):
    def test_parses_identity(self) -> None:
        header = GbaHeader.from_bytes(make_gba_header())

        self.assertEqual(header.title, "POKEMON FIRE")
        self.assertEqual(header.game_code, "BPRE")
        self.assertEqual(header.maker_code, "01")
        self.assertEqual(header.software_version, 0)

    def test_parses_a_non_default_software_version(self) -> None:
        header = GbaHeader.from_bytes(
            make_gba_header(game_code=b"BPGE", software_version=1)
        )

        self.assertEqual(header.game_code, "BPGE")
        self.assertEqual(header.software_version, 1)

    def test_rejects_short_header(self) -> None:
        with self.assertRaises(InvalidRomError):
            GbaHeader.from_bytes(b"BPRE")

    def test_rejects_an_invalid_fixed_byte(self) -> None:
        data = bytearray(make_gba_header())
        data[0xB2] = 0x00

        with self.assertRaisesRegex(InvalidRomError, "fixed byte"):
            GbaHeader.from_bytes(bytes(data))

    def test_rejects_an_invalid_checksum(self) -> None:
        data = bytearray(make_gba_header())
        data[0xBD] ^= 0xFF

        with self.assertRaisesRegex(InvalidRomError, "checksum"):
            GbaHeader.from_bytes(bytes(data))


if __name__ == "__main__":
    unittest.main()
