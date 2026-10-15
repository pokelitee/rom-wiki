from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.abilities import build_ability_dataset
from romwiki.sources import PokeDBGeneration


class AbilityDatasetTests(unittest.TestCase):
    def test_builds_rom_named_abilities_and_deduplicates_matching_slots(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[65] = "Overgrow"
        pokedb = _pokedb()
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "dataset": "pokemon",
                "source": {"archive": "personal.narc"},
                "name_sources": {
                    "ability_names": {"archive": "messages.narc", "member": 610}
                },
                "ability_names": names,
                "records": [
                    {
                        "member": 1,
                        "national_dex_id": 1,
                        "slug": "bulbasaur",
                        "name": "Bulbasaur",
                        "public": True,
                        "abilities": [
                            {"id": 65, "slug": "overgrow", "name": "Overgrow"},
                            {"id": 65, "slug": "overgrow", "name": "Overgrow"},
                        ],
                    },
                    {
                        "member": 500,
                        "national_dex_id": None,
                        "slug": "internal",
                        "name": "Internal",
                        "public": False,
                        "abilities": [
                            {"id": 1, "slug": "stench", "name": "Stench"},
                            {"id": 0, "slug": None, "name": None},
                        ],
                    },
                ],
            },
            pokedb,
        )

        overgrow = dataset["records"][64]
        self.assertEqual(dataset["record_count"], 123)
        self.assertEqual(dataset["assigned_record_count"], 1)
        self.assertEqual(overgrow["name"], "Overgrow")
        self.assertEqual(overgrow["slug"], "overgrow")
        self.assertEqual(overgrow["pokemon"][0]["slots"], [1, 2])
        self.assertEqual(dataset["records"][0]["pokemon"], [])

    def test_builds_hgss_abilities_from_rom_names_and_assignments(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[14] = "Compoundeyes"
        dataset = build_ability_dataset(
            {
                "game": "heartgold-us",
                "engine": "gen4_hgss",
                "dataset": "pokemon",
                "source": {"archive": "a/0/0/2"},
                "name_sources": {
                    "ability_names": {"archive": "a/0/2/7", "member": 720}
                },
                "ability_names": names,
                "records": [
                    {
                        "member": 12,
                        "national_dex_id": 12,
                        "slug": "butterfree",
                        "name": "Butterfree",
                        "public": True,
                        "abilities": [
                            {
                                "id": 14,
                                "slug": "compound-eyes",
                                "name": "Compoundeyes",
                                "is_hidden": False,
                            }
                        ],
                    }
                ],
            },
            _pokedb(),
        )

        compound_eyes = dataset["records"][13]
        self.assertEqual(compound_eyes["name"], "Compoundeyes")
        self.assertEqual(compound_eyes["slug"], "compound-eyes")
        self.assertEqual(compound_eyes["pokemon"][0]["slug"], "butterfree")
        self.assertEqual(dataset["name_source"], {"archive": "a/0/2/7", "member": 720})

    def test_carries_the_hidden_ability_flag_through_to_pokemon_entries(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[65] = "Overgrow"
        names[34] = "Chlorophyll"
        pokedb = _pokedb()
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "dataset": "pokemon",
                "source": {"archive": "personal.narc"},
                "ability_names": names,
                "records": [
                    {
                        "member": 1,
                        "national_dex_id": 1,
                        "slug": "bulbasaur",
                        "name": "Bulbasaur",
                        "public": True,
                        "abilities": [
                            {
                                "id": 65,
                                "slug": "overgrow",
                                "name": "Overgrow",
                                "is_hidden": False,
                            },
                            {"id": 0, "slug": None, "name": None, "is_hidden": False},
                            {
                                "id": 34,
                                "slug": "chlorophyll",
                                "name": "Chlorophyll",
                                "is_hidden": True,
                            },
                        ],
                    },
                ],
            },
            pokedb,
        )

        overgrow = dataset["records"][64]
        chlorophyll = dataset["records"][33]
        self.assertEqual(overgrow["pokemon"][0]["slots"], [1])
        self.assertFalse(overgrow["pokemon"][0]["is_hidden"])
        self.assertEqual(chlorophyll["pokemon"][0]["slots"], [3])
        self.assertTrue(chlorophyll["pokemon"][0]["is_hidden"])

    def test_attaches_pickup_tables_to_pickup_and_honey_gather_only(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[53] = "Pickup"
        names[118] = "Honey Gather"
        pokedb = _pokedb()
        pickup_dataset = {
            "tables": {
                "common_items": [{"item_id": 17, "name": "Potion"}],
                "rare_items": [{"item_id": 92, "name": "Nugget"}],
                "common_rate": [30],
                "honey_gather_rate": [5],
            }
        }
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "dataset": "pokemon",
                "source": {"archive": "personal.narc"},
                "ability_names": names,
                "records": [],
            },
            pokedb,
            pickup_dataset,
        )

        pickup = dataset["records"][52]
        honey_gather = dataset["records"][117]
        other = dataset["records"][64]
        self.assertEqual(pickup["slug"], "pickup")
        self.assertEqual(
            pickup["pickup"],
            {
                "common_items": [{"item_id": 17, "name": "Potion"}],
                "rare_items": [{"item_id": 92, "name": "Nugget"}],
                "common_rate": [30],
            },
        )
        self.assertEqual(honey_gather["slug"], "honey-gather")
        self.assertEqual(honey_gather["pickup"], {"honey_gather_rate": [5]})
        self.assertIsNone(other["pickup"])

    def test_attaches_gen5_level_ranges_to_pickup_only(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[53] = "Pickup"
        names[118] = "Honey Gather"
        pokedb = _pokedb()
        pickup_dataset = {
            "engine": "gen5_bw",
            "level_ranges": [
                {
                    "minimum_level": 1,
                    "maximum_level": 10,
                    "slots": [{"item_id": 17, "name": "Potion", "chance": 30}],
                }
            ],
        }
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "dataset": "pokemon",
                "source": {"archive": "personal.narc"},
                "ability_names": names,
                "records": [],
            },
            pokedb,
            pickup_dataset,
        )

        pickup = dataset["records"][52]
        honey_gather = dataset["records"][117]
        self.assertEqual(
            pickup["pickup"],
            {
                "level_ranges": [
                    {
                        "minimum_level": 1,
                        "maximum_level": 10,
                        "slots": [{"item_id": 17, "name": "Potion", "chance": 30}],
                    }
                ]
            },
        )
        self.assertIsNone(honey_gather["pickup"])


def _pokedb() -> PokeDBGeneration:
    ability_names = {
        ability_id: f"ability-{ability_id}" for ability_id in range(1, 124)
    }
    ability_names[1] = "stench"
    ability_names[14] = "compound-eyes"
    ability_names[65] = "overgrow"
    ability_names[53] = "pickup"
    ability_names[118] = "honey-gather"
    return PokeDBGeneration(
        pokemon_by_id={},
        pokemon_by_name={},
        pokemon_by_species={},
        abilities_by_id=ability_names,
        items_by_id={},
    )


if __name__ == "__main__":
    unittest.main()
