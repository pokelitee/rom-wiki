from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.components import display_name, evolution_condition


class DisplayNameTests(unittest.TestCase):
    def test_preserves_domain_specific_capitalization(self) -> None:
        expected_names = {
            "poke-balls": "Poké Balls",
            "poke-radar": "Poké Radar",
            "tm-hm": "TM / HM",
            "vs-recorder": "Vs. Recorder",
            "vs-seeker": "Vs. Seeker",
        }

        for value, expected in expected_names.items():
            with self.subTest(value=value):
                self.assertEqual(display_name(value), expected)

    def test_title_cases_regular_slug(self) -> None:
        self.assertEqual(display_name("evolution-stone"), "Evolution Stone")


class EvolutionConditionTests(unittest.TestCase):
    def test_links_party_species_parameter(self) -> None:
        entry = {
            "method": {"id": 21, "name": "level-with-party-species"},
            "parameter_data": {
                "kind": "pokemon",
                "id": 224,
                "slug": "remoraid",
                "name": "Remoraid",
            },
        }

        condition = evolution_condition(entry, "pokemon/mantyke/")

        self.assertEqual(
            condition,
            'Level up with <a href="../remoraid/">Remoraid</a> in the party',
        )


if __name__ == "__main__":
    unittest.main()
