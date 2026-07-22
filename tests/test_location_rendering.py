from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from romwiki.renderers.mkdocs import render_location_pages
from romwiki.renderers.mkdocs.references import ReferenceIndex


class LocationRenderingTests(unittest.TestCase):
    def test_renders_navigation_encounters_and_trainers(self) -> None:
        record = {
            "header_id": 45,
            "internal_name": "C03",
            "location_name_id": 7,
            "name": "Oreburgh City",
            "matrix_id": 0,
            "event_file_id": 42,
            "encounter_id": 3,
            "trainers": [
                {
                    "trainer_id": 246,
                    "name": "Roark",
                    "class_name": "Leader",
                    "source": "map-script",
                }
            ],
            "items": [
                {
                    "item_id": 17,
                    "name": "Potion",
                    "kind": "visible",
                    "event_index": 2,
                    "x": 8,
                    "z": 11,
                    "y": 0,
                    "hidden_flag": 400,
                },
                {
                    "item_id": 81,
                    "name": "Moon Stone",
                    "kind": "hidden",
                    "event_index": 0,
                    "x": 12,
                    "z": 5,
                    "y": 0,
                    "hidden_flag": None,
                },
            ],
            "shops": [
                {
                    "kind": "specialty",
                    "inventory_id": 1,
                    "script_file_id": 51,
                    "command_offset": 54,
                    "items": [
                        {
                            "item_id": 46,
                            "name": "Protein",
                            "price": 9800,
                            "required_badges": None,
                        }
                    ],
                },
                {
                    "kind": "frontier",
                    "currency": "bp",
                    "inventory_id": 0,
                    "script_file_id": 51,
                    "command_offset": 70,
                    "items": [
                        {
                            "item_id": 333,
                            "name": "TM06",
                            "price": 32,
                            "required_badges": None,
                        }
                    ],
                }
            ],
            "pokemon_gifts": [
                {
                    "kind": "egg",
                    "species_id": 175,
                    "name": "Togepi",
                    "level": 1,
                    "held_item_id": None,
                    "held_item_name": None,
                    "script_file_id": 51,
                    "command_offset": 90,
                }
            ],
            "static_encounters": [
                {
                    "species_id": 479,
                    "name": "Rotom",
                    "level": 20,
                    "command": "WildBattle",
                    "script_file_id": 51,
                    "command_offset": 104,
                }
            ],
            "warps": [
                {
                    "index": 0,
                    "x": 10,
                    "z": 20,
                    "destination_header_id": 47,
                    "destination_warp_id": 0,
                    "destination_name": "Oreburgh City",
                    "destination_internal_name": "C03GYM0101",
                    "destination_warp_exists": True,
                    "dynamic": False,
                }
            ],
            "connections": [
                {
                    "destination_header_id": 344,
                    "destination_name": "Route 203",
                    "destination_internal_name": "R203",
                    "directions": ["west"],
                }
            ],
        }
        dataset = {"records": [record]}
        references = ReferenceIndex.from_datasets(
            {
                "pokemon": {
                    "records": [
                        {
                            "public": True,
                            "member": 175,
                            "national_dex_id": 175,
                            "name": "Togepi",
                            "slug": "togepi",
                            "sprite": {"url": "https://example.test/togepi.png"},
                        },
                        {
                            "public": True,
                            "member": 479,
                            "national_dex_id": 479,
                            "name": "Rotom",
                            "slug": "rotom",
                            "sprite": {"url": "https://example.test/rotom.png"},
                        },
                    ]
                },
                "items": {
                    "records": [
                        {
                            "item_id": 17,
                            "name": "Potion",
                            "slug": "potion",
                            "reference": {
                                "sprite_url": "https://example.test/potion.png"
                            },
                        },
                        {"item_id": 81, "name": "Moon Stone", "slug": "moon-stone"},
                        {"item_id": 46, "name": "Protein", "slug": "protein"},
                        {"item_id": 333, "name": "TM06", "slug": "tm06"},
                    ]
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "header-999.md"
            stale_page.parent.mkdir(parents=True, exist_ok=True)
            stale_page.write_text("stale", encoding="utf-8")

            count = render_location_pages(dataset, output, references=references)
            page = (output / "header-045.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertFalse(stale_page.exists())
        self.assertIn("../encounters/area-003.md", page)
        self.assertIn("../trainers/trainer-0246.md", page)
        self.assertIn("| Visible | [Potion](../items/potion.md) | 17 | (8, 11) |", page)
        self.assertIn("[Moon Stone](../items/moon-stone.md)", page)
        self.assertIn('src="https://example.test/potion.png"', page)
        self.assertIn('src="https://example.test/togepi.png"', page)
        self.assertIn('src="https://example.test/rotom.png"', page)
        self.assertIn("rw-table-sprite--empty", page)
        self.assertIn("| [Protein](../items/protein.md) | 46 | ₽9,800 | Always |", page)
        self.assertIn("### Battle Frontier shop", page)
        self.assertIn("| [TM06](../items/tm06.md) | 333 | 32 BP | Always |", page)
        self.assertIn("| [Togepi](../pokemon/togepi.md) | Egg | 1 | — |", page)
        self.assertIn("| [Rotom](../pokemon/rotom.md) | 20 |", page)
        self.assertIn("header-047.md", page)
        self.assertIn("header-344.md", page)
        self.assertEqual(catalog["kind"], "locations")
        self.assertIn("shops", catalog["records"][0]["features"])


if __name__ == "__main__":
    unittest.main()
