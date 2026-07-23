from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt.messages import parse_english_message_archive
from romwiki.util.errors import InvalidRomError

from tests.engines.gen4_dppt.test_map_headers import _make_message_archive


def _make_raw_message_archive(
    messages: list[list[int]], *, archive_key: int = 0xA06
) -> bytes:
    """Like `_make_message_archive`, but with each message's raw code-point
    values (pre-character-lookup) supplied directly instead of encoded text.
    """
    table_end = 4 + len(messages) * 8
    encoded_messages = []
    for index, values in enumerate(messages):
        key = (0x91BD3 * (index + 1)) & 0xFFFF
        encoded = bytearray()
        for value in values:
            encoded.extend(struct.pack("<H", value ^ key))
            key = (key + 0x493D) & 0xFFFF
        encoded_messages.append(bytes(encoded))

    result = bytearray(struct.pack("<HH", len(messages), archive_key))
    offset = table_end
    for index, encoded in enumerate(encoded_messages):
        entry_key = (archive_key * 0x2FD * (index + 1)) & 0xFFFF
        entry_mask = entry_key | entry_key << 16
        result.extend(
            struct.pack(
                "<II",
                offset ^ entry_mask,
                (len(encoded) // 2) ^ entry_mask,
            )
        )
        offset += len(encoded)
    result.extend(b"".join(encoded_messages))
    return bytes(result)


class Gen4MessageErrorTests(unittest.TestCase):
    def test_rejects_an_archive_smaller_than_its_header(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "too small"):
            parse_english_message_archive(b"\x00\x00\x00")

    def test_rejects_a_truncated_pointer_table(self) -> None:
        # Declares 2 messages but only provides header bytes, no table.
        data = struct.pack("<HH", 2, 0xA06)
        with self.assertRaisesRegex(InvalidRomError, "pointer table is truncated"):
            parse_english_message_archive(data)

    def test_rejects_a_limit_beyond_the_message_count(self) -> None:
        data = _make_message_archive(("Table", "Description"))
        with self.assertRaisesRegex(InvalidRomError, "limit is out of bounds"):
            parse_english_message_archive(data, limit=3)

    def test_rejects_a_negative_limit(self) -> None:
        data = _make_message_archive(("Table", "Description"))
        with self.assertRaisesRegex(InvalidRomError, "limit is out of bounds"):
            parse_english_message_archive(data, limit=-1)

    def test_rejects_a_message_extending_outside_the_archive(self) -> None:
        data = bytearray(_make_message_archive(("Table",)))
        # Corrupt the one entry's decoded length so it reads past the buffer.
        entry_key = (0xA06 * 0x2FD * 1) & 0xFFFF
        entry_mask = entry_key | entry_key << 16
        offset, _length = struct.unpack_from("<II", data, 4)
        struct.pack_into("<II", data, 4, offset, 1000 ^ entry_mask)
        with self.assertRaisesRegex(InvalidRomError, "extends outside its archive"):
            parse_english_message_archive(bytes(data))

    def test_rejects_an_unsupported_character_code(self) -> None:
        data = _make_raw_message_archive([[0x1FE, 0xFFFF]])
        with self.assertRaisesRegex(
            InvalidRomError, "Unsupported English Gen IV character code"
        ):
            parse_english_message_archive(data)

    def test_rejects_compressed_text_with_no_terminator(self) -> None:
        # 0xF100 marker followed by one 9-bit chunk (value 1, not 0x1FF) that
        # neither aligns to a full byte nor forms a terminator-prefix pattern,
        # and the message ends without ever emitting the outer 0xFFFF marker.
        data = _make_raw_message_archive([[0xF100, 0b1]])
        with self.assertRaisesRegex(InvalidRomError, "no terminator"):
            parse_english_message_archive(data)


if __name__ == "__main__":
    unittest.main()
