from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.text import (
    decode_gen3_text,
    decode_gen3_text_sequence,
    decode_gen3_text_table,
)


class DecodeGen3TextTests(unittest.TestCase):
    def test_decodes_uppercase_words_with_a_space(self) -> None:
        # P O U N D
        data = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF])
        self.assertEqual(decode_gen3_text(data), "POUND")

    def test_decodes_a_two_word_uppercase_name(self) -> None:
        # T A C K L E space B A L L
        data = bytes(
            [
                0xCE,
                0xBB,
                0xBD,
                0xC5,
                0xC6,
                0xBF,
                0x00,
                0xBC,
                0xBB,
                0xC6,
                0xC6,
                0xFF,
            ]
        )
        self.assertEqual(decode_gen3_text(data), "TACKLE BALL")

    def test_decodes_digits(self) -> None:
        # 1 2 3
        data = bytes([0xA2, 0xA3, 0xA4, 0xFF])
        self.assertEqual(decode_gen3_text(data), "123")

    def test_stops_at_the_terminator(self) -> None:
        data = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF, 0xCA, 0xC9])
        self.assertEqual(decode_gen3_text(data), "POUND")

    def test_stops_at_the_end_of_data_without_a_terminator(self) -> None:
        data = bytes([0xCA, 0xC9])
        self.assertEqual(decode_gen3_text(data), "PO")

    def test_decodes_a_period(self) -> None:
        # M T . space M O O N
        data = bytes([0xC7, 0xCE, 0xAD, 0x00, 0xC7, 0xC9, 0xC9, 0xC8, 0xFF])
        self.assertEqual(decode_gen3_text(data), "MT. MOON")


class DecodeGen3TextTableTests(unittest.TestCase):
    def test_decodes_a_fixed_width_table(self) -> None:
        entry_a = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF, 0x00, 0x00])
        entry_b = bytes([0xCE, 0xBB, 0xBD, 0xC5, 0xC6, 0xBF, 0xFF, 0x00])
        data = entry_a + entry_b

        names = decode_gen3_text_table(data, stride=8, count=2)

        self.assertEqual(names, ["POUND", "TACKLE"])


class DecodeGen3TextSequenceTests(unittest.TestCase):
    def test_decodes_back_to_back_variable_length_strings(self) -> None:
        entry_a = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF])
        entry_b = bytes([0xCE, 0xBB, 0xBD, 0xC5, 0xC6, 0xBF, 0xFF])
        data = entry_a + entry_b

        names = decode_gen3_text_sequence(data, offset=0, count=2)

        self.assertEqual(names, ["POUND", "TACKLE"])

    def test_starts_decoding_at_the_given_offset(self) -> None:
        entry_a = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF])
        entry_b = bytes([0xCE, 0xBB, 0xBD, 0xC5, 0xC6, 0xBF, 0xFF])
        data = entry_a + entry_b

        names = decode_gen3_text_sequence(data, offset=len(entry_a), count=1)

        self.assertEqual(names, ["TACKLE"])


if __name__ == "__main__":
    unittest.main()
