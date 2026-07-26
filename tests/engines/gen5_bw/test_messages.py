from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.messages import parse_english_message_archive
from romwiki.util.errors import InvalidRomError

_BASE = 16  # header (12 bytes) + one section_offset entry (4 bytes)


def _ror16(value: int, bits: int) -> int:
    value &= 0xFFFF
    return ((value >> bits) | (value << (16 - bits))) & 0xFFFF


def _encrypt(plain_words: list[int]) -> list[int]:
    # Inverse of messages.py's decrypt loop: the last raw word is arbitrary
    # (decrypting it always yields the terminator by construction), so pick 0
    # and roll the same key schedule forward across the rest of the message.
    raw = [0] * len(plain_words)
    key = 0 ^ 0xFFFF
    for position in range(len(plain_words) - 1, -1, -1):
        raw[position] = plain_words[position] ^ key
        key = _ror16(key, 3)
    return raw


def _make_message_archive(messages: tuple[str, ...]) -> bytes:
    entry_count = len(messages)
    table_start = _BASE + 4
    offset_cursor = 4 + entry_count * 8  # relative to _BASE
    entries: list[tuple[int, int]] = []
    bodies: list[bytes] = []
    for text in messages:
        plain_words = [ord(character) for character in text] + [0xFFFF]
        raw_words = _encrypt(plain_words)
        body = b"".join(struct.pack("<H", word) for word in raw_words)
        entries.append((offset_cursor, len(raw_words)))
        bodies.append(body)
        offset_cursor += len(body)

    header = struct.pack("<HHII", 1, entry_count, 0, 0)
    section_offsets = struct.pack("<I", _BASE)
    size_repeat = struct.pack("<I", 0)
    pointer_table = b"".join(
        struct.pack("<IHH", offset, count, 0) for offset, count in entries
    )
    assert len(header) + len(section_offsets) == _BASE
    assert table_start == _BASE + len(size_repeat)
    return header + section_offsets + size_repeat + pointer_table + b"".join(bodies)


def _make_raw_message_archive(messages: list[list[int]]) -> bytes:
    """Like `_make_message_archive`, but with each message's plaintext code
    points supplied directly (no terminator appended automatically)."""
    entry_count = len(messages)
    offset_cursor = 4 + entry_count * 8
    entries: list[tuple[int, int]] = []
    bodies: list[bytes] = []
    for plain_words in messages:
        raw_words = _encrypt(plain_words)
        body = b"".join(struct.pack("<H", word) for word in raw_words)
        entries.append((offset_cursor, len(raw_words)))
        bodies.append(body)
        offset_cursor += len(body)

    header = struct.pack("<HHII", 1, entry_count, 0, 0)
    section_offsets = struct.pack("<I", _BASE)
    size_repeat = struct.pack("<I", 0)
    pointer_table = b"".join(
        struct.pack("<IHH", offset, count, 0) for offset, count in entries
    )
    return header + section_offsets + size_repeat + pointer_table + b"".join(bodies)


class Gen5MessageTests(unittest.TestCase):
    def test_decodes_real_shaped_names(self) -> None:
        data = _make_message_archive(("Bulbasaur", "Mr. Mime", "Poké Ball"))

        result = parse_english_message_archive(data)

        self.assertEqual(result, ("Bulbasaur", "Mr. Mime", "Poké Ball"))

    def test_limit_truncates_to_the_first_n_messages(self) -> None:
        data = _make_message_archive(("Bulbasaur", "Ivysaur", "Venusaur"))

        result = parse_english_message_archive(data, limit=2)

        self.assertEqual(result, ("Bulbasaur", "Ivysaur"))

    def test_rejects_an_archive_smaller_than_its_header(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "too small"):
            parse_english_message_archive(b"\x00" * 8)

    def test_rejects_a_limit_beyond_the_message_count(self) -> None:
        data = _make_message_archive(("Bulbasaur",))
        with self.assertRaisesRegex(InvalidRomError, "limit is out of bounds"):
            parse_english_message_archive(data, limit=3)

    def test_rejects_a_negative_limit(self) -> None:
        data = _make_message_archive(("Bulbasaur",))
        with self.assertRaisesRegex(InvalidRomError, "limit is out of bounds"):
            parse_english_message_archive(data, limit=-1)

    def test_rejects_a_truncated_pointer_table(self) -> None:
        data = _make_message_archive(("Bulbasaur", "Ivysaur"))
        with self.assertRaisesRegex(InvalidRomError, "pointer table is truncated"):
            parse_english_message_archive(data[:20])

    def test_rejects_a_message_extending_outside_the_archive(self) -> None:
        data = bytearray(_make_message_archive(("Bulbasaur",)))
        # Corrupt the one entry's char count so it reads past the buffer.
        offset, _count, unknown = struct.unpack_from("<IHH", data, _BASE + 4)
        struct.pack_into("<IHH", data, _BASE + 4, offset, 1000, unknown)
        with self.assertRaisesRegex(InvalidRomError, "extends outside its archive"):
            parse_english_message_archive(bytes(data))

    def test_rejects_an_unsupported_character_code(self) -> None:
        data = _make_raw_message_archive([[0x0010, 0xFFFF]])
        with self.assertRaisesRegex(
            InvalidRomError, "Unsupported Gen V character code"
        ):
            parse_english_message_archive(data)

    def test_decodes_a_variable_code_as_a_placeholder(self) -> None:
        # Real Black ROM map-name table (member 89, entry 3, unused by any
        # actual map): two variable codes around a literal "'s ".
        words = [
            0xF000,
            0x0100,
            0x0001,
            0x0000,
            ord("'"),
            ord("s"),
            ord(" "),
            0xF000,
            0x0105,
            0x0001,
            0x0001,
            0xFFFF,
        ]
        data = _make_raw_message_archive([words])

        result = parse_english_message_archive(data)

        self.assertEqual(result, ("{VAR:0100}'s {VAR:0105}",))

    def test_rejects_a_truncated_variable_code(self) -> None:
        words = [0xF000, 0x0100, 0x0005, 0xFFFF]
        data = _make_raw_message_archive([words])
        with self.assertRaisesRegex(InvalidRomError, "truncated variable code"):
            parse_english_message_archive(data)

    def test_decodes_a_line_break_as_a_newline(self) -> None:
        # Real Black ROM item-description fact (member 53, index 149, Cheri
        # Berry): "If held by a Pokémon, \nit recovers from paralysis." --
        # this control code is what makes the description wrap to a second
        # line rather than being one continuous string.
        words = (
            [ord(c) for c in "If held, "]
            + [0xFFFE]
            + [ord(c) for c in "it recovers."]
            + [0xFFFF]
        )
        data = _make_raw_message_archive([words])

        result = parse_english_message_archive(data)

        self.assertEqual(result, ("If held, \nit recovers.",))

    def test_decodes_compressed_text(self) -> None:
        # 9-bit-packed stream (all 16 bits/word) for "AB": codes 0x41, 0x42,
        # then a value whose low byte is 0xFF to terminate the bitstream. The
        # decrypt algorithm forces the *last* raw word to always decode to
        # 0xFFFF regardless of content, so the packed bits must live entirely
        # in the words between the leading 0xF100 marker and that trailing
        # forced terminator (unread once the bitstream self-terminates).
        packed = 0x41 | (0x42 << 9) | (0x1FF << 18)
        words = [0xF100, packed & 0xFFFF, (packed >> 16) & 0xFFFF, 0xFFFF]
        data = _make_raw_message_archive([words])

        result = parse_english_message_archive(data)

        self.assertEqual(result, ("AB",))


if __name__ == "__main__":
    unittest.main()
