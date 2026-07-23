from __future__ import annotations

import string
import struct
import unittest

from romwiki.engines.gen4_dppt import (
    parse_english_message_archive,
    parse_platinum_map_headers,
)
from romwiki.util.errors import InvalidRomError


class Gen4MapHeaderTests(unittest.TestCase):
    def test_decodes_header_linkage_and_internal_name(self) -> None:
        data = bytearray(24)
        data[0x0] = 5
        data[0x1] = 1
        struct.pack_into("<H", data, 0x2, 18)
        struct.pack_into("<HHH", data, 0x4, 427, 12, 433)
        struct.pack_into("<HH", data, 0xA, 1103, 1119)
        struct.pack_into("<H", data, 0xE, 42)
        struct.pack_into("<H", data, 0x10, 328)
        data[0x12] = 7
        data[0x13] = 3
        data[0x14] = 2
        data[0x15] = 4
        struct.pack_into("<H", data, 0x16, 0x0304)

        headers = parse_platinum_map_headers(
            bytes(data), b"W201\0" + bytes(11), count=1
        )

        self.assertEqual(headers[0].header_id, 0)
        self.assertEqual(headers[0].area_data_id, 5)
        self.assertEqual(headers[0].unknown_value, 1)
        self.assertEqual(headers[0].matrix_id, 18)
        self.assertEqual(headers[0].encounter_id, 42)
        self.assertEqual(headers[0].script_file_id, 427)
        self.assertEqual(headers[0].level_script_id, 12)
        self.assertEqual(headers[0].text_archive_id, 433)
        self.assertEqual(headers[0].day_music_id, 1103)
        self.assertEqual(headers[0].night_music_id, 1119)
        self.assertEqual(headers[0].event_file_id, 328)
        self.assertEqual(headers[0].location_name_id, 7)
        self.assertEqual(headers[0].map_label_window_id, 3)
        self.assertEqual(headers[0].weather_id, 2)
        self.assertEqual(headers[0].camera_id, 4)
        self.assertEqual(headers[0].flags, 0x0304)
        self.assertEqual(headers[0].internal_name, "W201")

    def test_rejects_mismatched_table_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_platinum_map_headers(bytes(23), bytes(16), count=1)


class Gen4MessageTests(unittest.TestCase):
    def test_can_limit_decoding_to_a_message_prefix(self) -> None:
        data = _make_message_archive(("Table", "Description"))

        self.assertEqual(parse_english_message_archive(data, limit=1), ("Table",))

    def test_decrypts_english_location_names(self) -> None:
        data = _make_message_archive(("Twinleaf Town", "Pokémon League"))

        messages = parse_english_message_archive(data)

        self.assertEqual(messages, ("Twinleaf Town", "Pokémon League"))

    def test_decompresses_trainer_text(self) -> None:
        data = _make_compressed_message_archive("Tristan")

        self.assertEqual(parse_english_message_archive(data), ("Tristan",))

    def test_accepts_aligned_compressed_text_with_outer_terminator(self) -> None:
        data = _make_compressed_message_archive(
            "Vogan", truncate_compressed_terminator=True
        )

        self.assertEqual(parse_english_message_archive(data), ("Vogan",))

    def test_accepts_compressed_terminator_prefix_with_outer_terminator(self) -> None:
        data = _make_compressed_message_archive(
            "Trista", truncate_compressed_terminator=True
        )

        self.assertEqual(parse_english_message_archive(data), ("Trista",))


_ENCODING = {
    **{value: 0x121 + index for index, value in enumerate(string.digits)},
    **{value: 0x12B + index for index, value in enumerate(string.ascii_uppercase)},
    **{value: 0x145 + index for index, value in enumerate(string.ascii_lowercase)},
    "é": 0x188,
    " ": 0x1DE,
}


def _make_message_archive(messages: tuple[str, ...], archive_key: int = 0xA06) -> bytes:
    table_end = 4 + len(messages) * 8
    encoded_messages = []
    for index, message in enumerate(messages):
        key = (0x91BD3 * (index + 1)) & 0xFFFF
        encoded = bytearray()
        for value in [_ENCODING[character] for character in message] + [0xFFFF]:
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


def _make_compressed_message_archive(
    message: str, *, truncate_compressed_terminator: bool = False
) -> bytes:
    buffer = 0
    bit_count = 0
    words = []
    values = [_ENCODING[character] for character in message] + [0x1FF]
    for value in values:
        buffer |= value << bit_count
        bit_count += 9
        while bit_count >= 15:
            words.append(buffer & 0x7FFF)
            buffer >>= 15
            bit_count -= 15
    if bit_count and not truncate_compressed_terminator:
        words.append(buffer)

    key = 0x91BD3 & 0xFFFF
    encoded = bytearray()
    for value in [0xF100, *words, 0xFFFF]:
        encoded.extend(struct.pack("<H", value ^ key))
        key = (key + 0x493D) & 0xFFFF
    archive_key = 0xA06
    entry_key = (archive_key * 0x2FD) & 0xFFFF
    entry_mask = entry_key | entry_key << 16
    return (
        struct.pack("<HH", 1, archive_key)
        + struct.pack("<II", 12 ^ entry_mask, (len(encoded) // 2) ^ entry_mask)
        + encoded
    )


if __name__ == "__main__":
    unittest.main()
