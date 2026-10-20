from __future__ import annotations

import unittest

from romwiki.engines.gen4.shared.battle_variant_support import (
    resolved_battle_location,
    species_name,
)


class ResolvedBattleLocationTests(unittest.TestCase):
    def test_returns_the_shared_location_when_every_variant_agrees(self) -> None:
        records_by_id = {
            1: {"locations": [{"name": "Route 1"}]},
            2: {"locations": [{"name": "Route 1"}]},
        }

        self.assertEqual(resolved_battle_location(records_by_id, (1, 2)), "Route 1")

    def test_prefers_script_references_over_locations(self) -> None:
        records_by_id = {
            1: {
                "script_references": [{"name": "Route 1"}],
                "locations": [{"name": "Route 2"}],
            }
        }

        self.assertEqual(resolved_battle_location(records_by_id, (1,)), "Route 1")

    def test_returns_none_when_variants_disagree_on_location(self) -> None:
        records_by_id = {
            1: {"locations": [{"name": "Route 1"}]},
            2: {"locations": [{"name": "Route 2"}]},
        }

        self.assertIsNone(resolved_battle_location(records_by_id, (1, 2)))

    def test_returns_none_for_an_unresolved_trainer_id(self) -> None:
        records_by_id = {1: {"locations": [{"name": "Route 1"}]}}

        self.assertIsNone(resolved_battle_location(records_by_id, (1, 2)))

    def test_returns_none_when_a_record_has_no_location(self) -> None:
        records_by_id: dict[int, dict[str, list[str]]] = {1: {"locations": []}}

        self.assertIsNone(resolved_battle_location(records_by_id, (1,)))


class SpeciesNameTests(unittest.TestCase):
    def test_titles_a_name_from_an_indexed_table(self) -> None:
        names = ("bulbasaur", "ivysaur", "venusaur")

        self.assertEqual(species_name(names, 2), "Venusaur")

    def test_titles_a_name_from_a_mapped_table(self) -> None:
        names = {1: "bulbasaur", 644: "zekrom"}

        self.assertEqual(species_name(names, 644), "Zekrom")

    def test_falls_back_to_a_placeholder_for_an_unnamed_species(self) -> None:
        self.assertEqual(species_name(("bulbasaur",), 999), "species-999")
        self.assertEqual(species_name({1: "bulbasaur"}, 999), "species-999")


if __name__ == "__main__":
    unittest.main()
