from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.conditional_encounters import (
    append_daily_swarm,
    append_headbutt_encounters,
    append_hidden_grotto,
    append_safari_area,
)

_POKEMON = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
_ITEM = {"id": 1, "slug": "potion", "name": "Potion"}


def _headbutt_slot() -> dict[str, object]:
    return {
        "pokemon": _POKEMON,
        "minimum_level": 5,
        "maximum_level": 7,
        "chance": 50,
    }


def _pokemon(species_id: int) -> dict[str, object]:
    if species_id == 25:
        return _POKEMON
    return {"id": species_id, "slug": "eevee", "name": "Eevee", "sprite": None}


def _headbutt_value(species_id: int) -> dict[str, object]:
    return {
        "pools": {
            "common": [{**_headbutt_slot(), "pokemon": _pokemon(species_id)}],
            "rare": [],
            "secret": [],
        },
        "tree_groups": [{"group": 0, "kind": "regular", "coordinates": [(4, 8)]}],
    }


class HeadbuttRenderingTests(unittest.TestCase):
    def test_single_version_has_no_tabs_and_one_heading_each(self) -> None:
        record = {
            "version_variants": {"black": _headbutt_value(25)},
        }
        lines: list[str] = []

        append_headbutt_encounters(lines, record, "trainers/t.md", None)
        page = "\n".join(lines)

        self.assertEqual(page.count("#### Common trees"), 1)
        self.assertEqual(page.count("#### Tree groups"), 1)
        self.assertNotIn('=== "', page)

    def test_differing_versions_tab_the_table_not_the_heading(self) -> None:
        record = {
            "version_variants": {
                "black": _headbutt_value(25),
                "white": _headbutt_value(133),
            },
        }
        lines: list[str] = []

        append_headbutt_encounters(lines, record, "trainers/t.md", None)
        page = "\n".join(lines)

        # The heading is emitted once, not once per version tab (which would
        # produce duplicate/suffixed anchors in the page's table of contents).
        self.assertEqual(page.count("#### Common trees"), 1)
        self.assertEqual(page.count("#### Tree groups"), 1)
        self.assertIn('=== "Black"', page)
        self.assertIn('=== "White"', page)

    def test_identical_versions_collapse_without_tabs(self) -> None:
        record = {
            "version_variants": {
                "black": _headbutt_value(25),
                "white": _headbutt_value(25),
            },
        }
        lines: list[str] = []

        append_headbutt_encounters(lines, record, "trainers/t.md", None)
        page = "\n".join(lines)

        self.assertNotIn('=== "', page)


class DailySwarmRenderingTests(unittest.TestCase):
    def test_differing_versions_tab_without_duplicating_the_heading(self) -> None:
        record = {
            "version_variants": {
                "black": {
                    "pokemon": _POKEMON,
                    "minimum_level": 10,
                    "maximum_level": 10,
                },
                "white": {
                    "pokemon": _pokemon(133),
                    "minimum_level": 10,
                    "maximum_level": 10,
                },
            },
        }
        lines: list[str] = []

        append_daily_swarm(lines, record, "trainers/t.md", None)
        page = "\n".join(lines)

        self.assertEqual(page.count("Daily Swarm"), 1)
        self.assertIn('=== "Black"', page)
        self.assertIn('=== "White"', page)


class HiddenGrottoRenderingTests(unittest.TestCase):
    def _value(self, species_id: int) -> dict[str, object]:
        return {
            "pokemon": [
                {
                    "pokemon": _pokemon(species_id),
                    "minimum_level": 10,
                    "maximum_level": 12,
                    "female_percentage": 50,
                    "pool_chance": 25,
                    "group": 0,
                }
            ],
            "visible_items": [
                {"item": _ITEM, "pool_chance": 10, "group": 0},
            ],
            "hidden_items": [],
        }

    def test_differing_versions_tab_tables_not_headings(self) -> None:
        record = {
            "grotto_id": 1,
            "version_variants": {
                "black": self._value(25),
                "white": self._value(133),
            },
        }
        lines: list[str] = []

        append_hidden_grotto(lines, record, "locations/l.md", None)
        page = "\n".join(lines)

        self.assertEqual(page.count("#### Pokémon"), 1)
        self.assertEqual(page.count("#### Visible items"), 1)
        self.assertEqual(page.count("#### Hidden items"), 1)
        self.assertIn('=== "Black"', page)
        self.assertIn('=== "White"', page)


class SafariAreaRenderingTests(unittest.TestCase):
    def _value(self, species_id: int) -> dict[str, object]:
        slot = {"pokemon": _pokemon(species_id), "level": 5}
        return {
            "methods": {
                "grass": {
                    "base_pools": {
                        "morning": [slot],
                        "day": [slot],
                        "night": [slot],
                    },
                    "block_encounters": [],
                }
            }
        }

    def test_differing_versions_tab_tables_not_method_or_section_headings(
        self,
    ) -> None:
        record = {
            "area_name": "Plains",
            "version_variants": {
                "black": self._value(25),
                "white": self._value(133),
            },
        }
        lines: list[str] = []

        append_safari_area(lines, record, "encounters/e.md")
        page = "\n".join(lines)

        self.assertEqual(page.count("### Grass"), 1)
        self.assertEqual(page.count("#### Base encounters"), 1)
        self.assertEqual(page.count("#### Block encounters"), 1)
        self.assertIn('=== "Black"', page)
        self.assertIn('=== "White"', page)
