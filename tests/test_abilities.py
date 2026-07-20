from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

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
        self.assertIn("| #001 | 1 |", page)
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


def _pokedb() -> PokeDBGeneration:
    ability_names = {
        ability_id: f"ability-{ability_id}" for ability_id in range(1, 124)
    }
    ability_names[1] = "stench"
    ability_names[65] = "overgrow"
    return PokeDBGeneration(
        pokemon_by_id={},
        pokemon_by_name={},
        pokemon_by_species={},
        abilities_by_id=ability_names,
        items_by_id={},
    )


if __name__ == "__main__":
    unittest.main()
