from __future__ import annotations

import unittest

from romwiki.platforms.nds.blz import (
    blz_decompress,
    decompress_arm9,
    is_blz_compressed,
    strip_arm9_footer,
)
from romwiki.util.errors import InvalidRomError


class BlzDecompressTests(unittest.TestCase):
    def test_decodes_a_run_length_match(self) -> None:
        # 32 repeated 'A's, encoded with a real BLZ encoder (ported from
        # BLZCoder.java) -- exercises the LZ back-reference copy loop.
        data = bytes.fromhex("05500990033000004141411e140000080c000000")
        self.assertEqual(blz_decompress(data), b"A" * 32)

    def test_decodes_interleaved_literals_and_matches(self) -> None:
        data = bytes.fromhex(
            "542af0206a756d087073206f7665722000740b006c617a792064026f672e"
            "205468652000717569636b206272006f776e20666f782100ffff3f00000a"
            "01000000"
        )
        self.assertEqual(
            blz_decompress(data),
            b"The quick brown fox jumps over the lazy dog. The quick brown fox!",
        )

    def test_passes_through_uncompressed_data(self) -> None:
        # inc_len < 1 (the last 4 bytes, masked, are zero) means "not coded".
        data = b"raw data, no header" + b"\x00" * 4
        self.assertEqual(blz_decompress(data), data)

    def test_rejects_a_bad_header_length(self) -> None:
        data = bytearray(b"\x00" * 12)
        data[-5] = 0xFF  # outside the valid 0x08-0x0B range
        data[-4:] = (1).to_bytes(4, "little")
        with self.assertRaises(InvalidRomError):
            blz_decompress(bytes(data))


class Arm9FooterTests(unittest.TestCase):
    def test_strips_a_nitro_footer_block(self) -> None:
        body = b"code" * 4
        footer = (0xDEC00621).to_bytes(4, "little") + b"\x00" * 8
        self.assertEqual(strip_arm9_footer(body + footer), body)

    def test_strips_a_zero_footer_block(self) -> None:
        body = b"code" * 4
        footer = b"\x00" * 12
        self.assertEqual(strip_arm9_footer(body + footer), body)

    def test_leaves_data_without_a_footer_untouched(self) -> None:
        body = b"no footer here, just sixteen b."
        self.assertEqual(strip_arm9_footer(body), body)


class BlzCompressionDetectionTests(unittest.TestCase):
    def test_detects_a_plausible_compression_header(self) -> None:
        data = bytes.fromhex("05500990033000004141411e140000080c000000")
        self.assertTrue(is_blz_compressed(data))

    def test_rejects_data_too_short_to_carry_a_header(self) -> None:
        self.assertFalse(is_blz_compressed(b"short"))

    def test_rejects_an_implausible_header_length_byte(self) -> None:
        self.assertFalse(is_blz_compressed(b"\x00" * 20))


class DecompressArm9Tests(unittest.TestCase):
    def test_strips_footer_then_decompresses(self) -> None:
        compressed = bytes.fromhex(
            "05500990033000004141411e140000080c000000"
        )
        footer = (0xDEC00621).to_bytes(4, "little") + b"\x00" * 8
        self.assertEqual(decompress_arm9(compressed + footer), b"A" * 32)

    def test_returns_uncompressed_data_unchanged(self) -> None:
        data = b"plain uncompressed arm9 bytes"
        self.assertEqual(decompress_arm9(data), data)


if __name__ == "__main__":
    unittest.main()
