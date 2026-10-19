from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.text import (
    decode_gen3_name_table,
    decode_gen3_text,
    gen3_display_name,
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

    def test_decodes_species_name_punctuation(self) -> None:
        cases = {
            bytes([0xC0, 0xBB, 0xCC, 0xB4, 0xBE, 0xFF]): "FAR'D",
            bytes([0xC2, 0xC9, 0xAE, 0xC9, 0xC2, 0xFF]): "HO-OH",
            bytes([0xC8, 0xC3, 0xBE, 0xC9, 0xB6, 0xB5, 0xFF]): "NIDO\u2640\u2642",
            bytes([0xAB, 0xAC, 0xFF]): "!?",
        }
        for data, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(decode_gen3_text(data), expected)

    def test_decodes_the_five_glyph_pokeblock_word(self) -> None:
        # Emerald's "POKéBLOCK CASE".
        data = bytes([0x55, 0x56, 0x57, 0x58, 0x59, 0x00, 0xBD, 0xBB, 0xCD, 0xBF])
        self.assertEqual(gen3_display_name(decode_gen3_text(data)), "Pokéblock Case")


class DecodeGen3NameTableTests(unittest.TestCase):
    def test_decodes_a_fixed_width_table_as_display_names(self) -> None:
        entry_a = bytes([0xCA, 0xC9, 0xCF, 0xC8, 0xBE, 0xFF, 0x00, 0x00])
        entry_b = bytes([0xCE, 0xBB, 0xBD, 0xC5, 0xC6, 0xBF, 0xFF, 0x00])
        data = entry_a + entry_b

        names = decode_gen3_name_table(data, stride=8, count=2)

        self.assertEqual(names, ["Pound", "Tackle"])


class Gen3DisplayNameTests(unittest.TestCase):
    def test_recases_each_word_of_an_all_caps_name(self) -> None:
        cases = {
            "THUNDERPUNCH": "Thunderpunch",
            "KING'S ROCK": "King's Rock",
            "MT. MOON": "Mt. Moon",
            "S.S. TICKET": "S.S. Ticket",
            "TATE&LIZA": "Tate&Liza",
            "POKé BALL": "Poké Ball",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(gen3_display_name(value), expected)

    def test_keeps_machine_and_stat_acronyms_in_capitals(self) -> None:
        cases = {
            "TM01": "TM01",
            "TM CASE": "TM Case",
            "HP UP": "HP Up",
            "PP MAX": "PP Max",
            "PKMN TRAINER": "PKMN Trainer",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(gen3_display_name(value), expected)

    def test_keeps_names_that_already_have_lowercase_letters(self) -> None:
        self.assertEqual(gen3_display_name("Pokémon Center"), "Pokémon Center")
        self.assertEqual(gen3_display_name(""), "")


if __name__ == "__main__":
    unittest.main()
