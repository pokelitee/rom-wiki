from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.abilities import build_ability_dataset
from romwiki.renderers.mkdocs import render_ability_pages
from romwiki.sources import PokeDBGeneration


class AbilityDatasetTests(unittest.TestCase):
    def test_builds_rom_named_abilities_and_deduplicates_matching_slots(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[65] = "Overgrow"
        pokedb = _pokedb()
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
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

    def test_carries_the_hidden_ability_flag_through_to_pokemon_entries(self) -> None:
        names = [" -", *(f"Ability {ability_id}" for ability_id in range(1, 124))]
        names[65] = "Overgrow"
        names[34] = "Chlorophyll"
        pokedb = _pokedb()
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
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
                            {"id": 65, "slug": "overgrow", "name": "Overgrow", "is_hidden": False},
                            {"id": 0, "slug": None, "name": None, "is_hidden": False},
                            {"id": 34, "slug": "chlorophyll", "name": "Chlorophyll", "is_hidden": True},
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
                "engine": "gen4_dppt",
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
                "engine": "gen4_dppt",
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

    def test_renders_ability_page_and_catalog(self) -> None:
        dataset = {
            "records": [
                {
                    "ability_id": 65,
                    "slug": "overgrow",
                    "name": "Overgrow",
                    "pokemon": [
                        {
                            "member": 1,
                            "national_dex_id": 1,
                            "slug": "bulbasaur",
                            "name": "Bulbasaur",
                            "slots": [1],
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_ability_pages(dataset, output)
            page = (output / "overgrow.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Overgrow", page)
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn("| — | 1 |", page)
        self.assertEqual(catalog["kind"], "abilities")
        self.assertEqual(catalog["records"][0]["pokemon_count"], 1)
        self.assertEqual(catalog["records"][0]["status"], "assigned")
        self.assertEqual(
            catalog["records"][0]["pokemon_refs"],
            [{
                "kind": "pokemon",
                "id": 1,
                "label": "Bulbasaur",
                "url": "../pokemon/bulbasaur/",
            }],
        )

    def test_marks_the_hidden_ability_slot_on_the_ability_page(self) -> None:
        dataset = {
            "records": [
                {
                    "ability_id": 34,
                    "slug": "chlorophyll",
                    "name": "Chlorophyll",
                    "pokemon": [
                        {
                            "member": 1,
                            "national_dex_id": 1,
                            "slug": "bulbasaur",
                            "name": "Bulbasaur",
                            "slots": [3],
                            "is_hidden": True,
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_ability_pages(dataset, output)
            page = (output / "chlorophyll.md").read_text(encoding="utf-8")

        self.assertIn(
            '3<abbr class="rw-hidden-ability" title="Hidden Ability">*</abbr>',
            page,
        )

    def test_renders_pickup_and_honey_gather_sections(self) -> None:
        dataset = {
            "records": [
                {
                    "ability_id": 53,
                    "slug": "pickup",
                    "name": "Pickup",
                    "pokemon": [],
                    "pickup": {
                        "common_items": [{"item_id": 17, "name": "Potion"}],
                        "rare_items": [{"item_id": 92, "name": "Nugget"}],
                        "common_rate": [30],
                    },
                },
                {
                    "ability_id": 118,
                    "slug": "honey-gather",
                    "name": "Honey Gather",
                    "pokemon": [],
                    "pickup": {"honey_gather_rate": [5, 10]},
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_ability_pages(dataset, output)
            pickup_page = (output / "pickup.md").read_text(encoding="utf-8")
            honey_page = (output / "honey-gather.md").read_text(encoding="utf-8")

        self.assertIn("## Held items", pickup_page)
        self.assertIn("Potion</span> | 17 |", pickup_page)
        self.assertIn("Nugget</span> | 92 |", pickup_page)
        self.assertIn("## Honey generation chance", honey_page)
        self.assertIn("| 1–10 | 5% |", honey_page)
        self.assertIn("| 11–20 | 10% |", honey_page)


    def test_renders_gen5_pickup_level_ranges(self) -> None:
        dataset = {
            "records": [
                {
                    "ability_id": 53,
                    "slug": "pickup",
                    "name": "Pickup",
                    "pokemon": [],
                    "pickup": {
                        "level_ranges": [
                            {
                                "minimum_level": 1,
                                "maximum_level": 10,
                                "slots": [
                                    {"item_id": 17, "name": "Potion", "chance": 30},
                                    {"item_id": 92, "name": "Nugget", "chance": 1},
                                ],
                            },
                            {
                                "minimum_level": 91,
                                "maximum_level": 100,
                                "slots": [
                                    {"item_id": 41, "name": "Max Elixir", "chance": 1},
                                ],
                            },
                        ]
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_ability_pages(dataset, output)
            page = (output / "pickup.md").read_text(encoding="utf-8")

        self.assertIn("## Held items", page)
        self.assertIn("### Level 1–10", page)
        self.assertIn("### Level 91–100", page)
        self.assertIn("Potion</span> | 17 | 30% |", page)
        self.assertIn("Nugget</span> | 92 | 1% |", page)
        self.assertIn("Max Elixir</span> | 41 | 1% |", page)


def _pokedb() -> PokeDBGeneration:
    ability_names = {
        ability_id: f"ability-{ability_id}" for ability_id in range(1, 124)
    }
    ability_names[1] = "stench"
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
