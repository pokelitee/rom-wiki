from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.special_encounters import special_encounter_groups


class SpecialEncounterGroupTests(unittest.TestCase):
    def test_direct_groups_are_selected_by_semantic_fields(self) -> None:
        pokemon = {"id": 1, "name": "Bulbasaur"}

        groups = special_encounter_groups(
            {
                "land_swarm": pokemon,
                "surf_swarm": None,
                "hoenn_radio": [pokemon],
                "sinnoh_radio": [],
                "night_fishing": None,
                "fishing_swarm": None,
            }
        )

        self.assertEqual(
            [(group.label, group.method, group.condition) for group in groups],
            [
                ("Land swarm", "Walking", "land swarm"),
                ("Hoenn Sound radio", "Walking", "Hoenn Sound radio"),
            ],
        )
        self.assertEqual(groups[0].slots[0]["species_id"], 1)

    def test_slotted_and_direct_pokemon_share_one_slot_view(self) -> None:
        pokemon = {"id": 1, "name": "Bulbasaur"}
        slot = {"pokemon": pokemon, "species_id": 1, "level": 5, "chance": 20}

        groups = special_encounter_groups(
            {
                "swarm": [slot],
                "day": [],
                "night": [],
                "dual_slot": {"ruby": [slot]},
                "radar": [pokemon],
                "unown_forms": [],
            }
        )

        self.assertEqual(
            [group.key for group in groups], ["swarm", "dual_slot:ruby", "radar"]
        )
        self.assertTrue(groups[0].slotted)
        self.assertFalse(groups[-1].slotted)
        self.assertEqual(groups[-1].condition, "Poké Radar")


if __name__ == "__main__":
    unittest.main()
