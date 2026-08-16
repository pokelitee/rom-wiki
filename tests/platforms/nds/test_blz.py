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

    def test_rejects_an_encoded_length_larger_than_the_packed_data(self) -> None:
        data = bytearray(b"\x00" * 12)
        data[-8:-5] = (0xFFFFFF).to_bytes(3, "little")  # enc_len > pak_len
        data[-5] = 0x08
        data[-4:] = (1).to_bytes(4, "little")
        with self.assertRaises(InvalidRomError):
            blz_decompress(bytes(data))

    def test_rejects_a_stream_truncated_before_its_decoded_length(self) -> None:
        # A well-formed header claiming a decoded length (inc_len=10, for a
        # 19-byte raw_len) backed by a one-byte compressed region -- just a
        # flags byte selecting a literal copy, with no literal byte to
        # follow it. Decoding must run out of packed input before reaching
        # raw_end.
        data = bytearray(9)
        data[0] = 0x00  # flags: first bit 0 selects the literal-copy branch
        data[1:4] = (9).to_bytes(3, "little")  # enc_len
        data[4] = 0x08  # hdr_len
        data[5:9] = (10).to_bytes(4, "little")  # inc_len
        with self.assertRaises(InvalidRomError):
            blz_decompress(bytes(data))

    def test_rejects_an_out_of_range_back_reference(self) -> None:
        # dec_len=0, comp_len=3, so the compressed region is the first three
        # bytes: a flags byte selecting one match token, then a two-byte
        # distance field encoding the minimum possible distance (pos=3).
        # Issued as the very first token, with nothing yet written to the
        # output buffer (r=0), so pos=3 > r=0 is out of range.
        data = bytearray(11)
        data[0] = 0x00  # distance low byte (pre-invert)
        data[1] = 0x00  # distance high byte (middle byte -- untouched by invert)
        data[2] = 0x80  # flags byte (pre-invert)
        data[3:6] = (11).to_bytes(3, "little")  # enc_len
        data[6] = 0x08  # hdr_len
        data[7:11] = (45).to_bytes(4, "little")  # inc_len
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
        compressed = bytes.fromhex("05500990033000004141411e140000080c000000")
        footer = (0xDEC00621).to_bytes(4, "little") + b"\x00" * 8
        self.assertEqual(decompress_arm9(compressed + footer), b"A" * 32)

    def test_returns_uncompressed_data_unchanged(self) -> None:
        data = b"plain uncompressed arm9 bytes"
        self.assertEqual(decompress_arm9(data), data)


if __name__ == "__main__":
    unittest.main()
