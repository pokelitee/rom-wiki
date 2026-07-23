from __future__ import annotations

import unittest

from romwiki.util.text import name_slug, normalize_display_name, title_case_slug


class TextTests(unittest.TestCase):
    def test_name_slug_normalizes_rom_names(self) -> None:
        self.assertEqual(name_slug("King's Rock"), "king-s-rock")
        self.assertEqual(name_slug("Poké Ball"), "poke-ball")

    def test_title_case_slug(self) -> None:
        self.assertEqual(title_case_slug("mr-mime"), "Mr Mime")

    def test_normalize_display_name_recapitalizes_all_caps_names(self) -> None:
        self.assertEqual(normalize_display_name("MR. MIME"), "Mr. Mime")
        self.assertEqual(normalize_display_name("FARFETCH'D"), "Farfetch'd")
        self.assertEqual(normalize_display_name("HO-OH"), "Ho-Oh")
        self.assertEqual(normalize_display_name("PORYGON-Z"), "Porygon-Z")
        self.assertEqual(normalize_display_name("NIDORAN♀"), "Nidoran♀")
        self.assertEqual(normalize_display_name("MIME JR."), "Mime Jr.")

    def test_normalize_display_name_keeps_mixed_case_names(self) -> None:
        self.assertEqual(normalize_display_name("Mr. Mime"), "Mr. Mime")
        self.assertEqual(normalize_display_name("Wormadam"), "Wormadam")
        self.assertEqual(normalize_display_name("-----"), "-----")


if __name__ == "__main__":
    unittest.main()
