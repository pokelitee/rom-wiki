from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_location_pages
from romwiki.renderers.mkdocs.references import ReferenceIndex


class LocationRenderingTests(unittest.TestCase):
    def test_links_gen5_location_to_all_seasonal_encounter_variants(self) -> None:
        record = {
            "header_id": 6,
            "name": "Route 1",
            "encounter_map_index": 3,
            "matrix_id": 0,
            "provenance": {"archive": "a/0/1/2", "member": 6},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        nonseasonal_record = {
            **record,
            "header_id": 7,
            "name": "Dreamyard",
            "encounter_map_index": 4,
            "provenance": {"archive": "a/0/1/2", "member": 7},
        }
        encounters = [
            {
                "area_id": 8,
                "map_index": 3,
                "season": "spring",
                "name": "Route 1",
                "versions": ["black"],
            },
            {
                "area_id": 9,
                "map_index": 3,
                "season": "summer",
                "name": "Route 1",
                "versions": ["white"],
            },
            {
                "area_id": 10,
                "map_index": 4,
                "season": None,
                "name": "Dreamyard",
            },
        ]
        dataset = {
            "game": "test",
            "engine": "gen5_bw",
            "records": [record, nonseasonal_record],
        }
        relationships = build_relationship_index(
            {
                "locations": dataset,
                "encounters": {
                    "game": "test",
                    "records": encounters,
                },
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(
                dataset,
                output,
                relationships=relationships,
            )
            page = (output / "header-006.md").read_text(encoding="utf-8")
            nonseasonal_page = (output / "header-007.md").read_text(encoding="utf-8")

        self.assertIn("[Map 003 (Spring)](../encounters/map-003-spring.md)", page)
        self.assertIn("[Map 003 (Summer)](../encounters/map-003-summer.md)", page)
        self.assertIn("| Spring |", page)
        self.assertIn("| Black |", page)
        self.assertIn("Wild encounter table index | `3`", page)
        self.assertIn("[Map 004](../encounters/map-004.md)", nonseasonal_page)
        self.assertIn("| All |", nonseasonal_page)

    def test_renders_gen5_location_linked_and_dynamic_shops(self) -> None:
        record = {
            "header_id": 105,
            "name": "Driftveil City",
            "encounter_map_index": None,
            "matrix_id": 0,
            "provenance": {"archive": "a/0/1/2", "member": 105},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [
                {
                    "kind": "specialty",
                    "currency": "money",
                    "inventory_id": 3,
                    "items": [
                        {
                            "item_id": 36,
                            "name": "Heal Powder",
                            "price": 450,
                            "required_badges": None,
                        }
                    ],
                    "name": "Driftveil Herb Salesman",
                    "is_main_game": True,
                    "dynamic": False,
                },
                {
                    "kind": "common",
                    "currency": "money",
                    "inventory_id": 255,
                    "items": [],
                    "name": "Standard Poké Mart",
                    "is_main_game": True,
                    "dynamic": True,
                },
            ],
        }
        dataset = {"engine": "gen5_bw", "records": [record]}

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output)
            page = (output / "header-105.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("### Driftveil Herb Salesman", page)
        self.assertNotIn("### Driftveil Herb Salesman 1", page)
        self.assertIn("| 36 | ₽450 | Main game |", page)
        self.assertIn("### Standard Poké Mart", page)
        self.assertIn("Stock changes with badge progression", page)
        self.assertIn("shops", catalog["records"][0]["features"])

    def test_renders_navigation_encounters_and_trainers(self) -> None:
        record = {
            "header_id": 45,
            "internal_name": "C03",
            "location_name_id": 7,
            "name": "Oreburgh City",
            "matrix_id": 0,
            "area_data_id": 2,
            "level_script_id": 12,
            "text_archive_id": 433,
            "day_music_id": 1103,
            "night_music_id": 1119,
            "weather_id": 0,
            "camera_id": 3,
            "map_flags": 0x0304,
            "event_file_id": 42,
            "encounter_id": 3,
            "roaming_activations": [
                {
                    "slot": 2,
                    "species_id": 491,
                    "species_name": "Darkrai",
                    "script_file_id": 51,
                    "command_offset": 0x140,
                }
            ],
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
                },
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
            "honey_tree": {
                "common": [{"species_id": 175, "name": "Togepi"}],
                "uncommon": [{"species_id": 479, "name": "Rotom"}],
                "rare": [{"species_id": 175, "name": "Togepi"}],
            },
            "daily_encounter_pool": {
                "kind": "trophy_garden",
                "species": [{"species_id": 479, "name": "Rotom"}],
                "pre_national_dex_species": None,
            },
            "game_corner_prizes": [
                {"item_id": 17, "name": "Potion", "price": 1000},
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
        self.assertIn('<a href="#wild-encounters">Yes</a>', page)
        self.assertIn('<a href="#item-pickups">2</a>', page)
        self.assertIn('<a href="#shops">2</a>', page)
        self.assertNotIn("In-game trades", page)
        self.assertIn("../trainers/trainer-0246.md", page)
        self.assertIn(
            '| Visible | <span class="rw-cell-media">'
            '<img class="rw-table-sprite" src="https://example.test/potion.png" '
            'alt="" loading="lazy" referrerpolicy="no-referrer">'
            "[Potion](../items/potion.md)</span> | 17 | (8, 11) |",
            page,
        )
        self.assertIn("[Moon Stone](../items/moon-stone.md)", page)
        self.assertIn('src="https://example.test/potion.png"', page)
        self.assertIn('src="https://example.test/togepi.png"', page)
        self.assertIn('src="https://example.test/rotom.png"', page)
        self.assertIn("rw-table-sprite--empty", page)
        self.assertIn(
            '| <span class="rw-cell-media">'
            '<span class="rw-table-sprite rw-table-sprite--empty" aria-hidden="true">'
            "—</span>[Protein](../items/protein.md)</span> | 46 | ₽9,800 | Always |",
            page,
        )
        self.assertIn("### Battle Frontier shop", page)
        self.assertIn(
            '| <span class="rw-cell-media">'
            '<span class="rw-table-sprite rw-table-sprite--empty" aria-hidden="true">'
            "—</span>[TM06](../items/tm06.md)</span> | 333 | 32 BP | Always |",
            page,
        )
        self.assertIn(
            '| <span class="rw-cell-media">'
            '<img class="rw-table-sprite" src="https://example.test/togepi.png" '
            'alt="" loading="lazy" referrerpolicy="no-referrer">'
            "[Togepi](../pokemon/togepi.md)</span> | — | Egg | 1 | — |",
            page,
        )
        self.assertIn(
            '| <span class="rw-cell-media">'
            '<img class="rw-table-sprite" src="https://example.test/rotom.png" '
            'alt="" loading="lazy" referrerpolicy="no-referrer">'
            "[Rotom](../pokemon/rotom.md)</span> | — | 20 | `WildBattle` |",
            page,
        )
        self.assertIn("header-047.md", page)
        self.assertIn("header-344.md", page)
        self.assertIn("## Roaming activations", page)
        self.assertIn("Darkrai", page)
        self.assertIn("| 2 | `51@0x140` |", page)
        self.assertIn("| Music ID | day `1103`, night `1119` |", page)
        self.assertIn("| Weather ID | `0` |", page)
        self.assertIn("| Map flags | `0x0304` |", page)
        self.assertEqual(catalog["kind"], "locations")
        self.assertIn("shops", catalog["records"][0]["features"])
        self.assertIn("roaming", catalog["records"][0]["features"])
        self.assertIn("honey tree", catalog["records"][0]["features"])
        self.assertIn("daily rotation", catalog["records"][0]["features"])
        self.assertIn('<a href="#honey-tree">Yes</a>', page)
        self.assertIn('<a href="#trophy-garden-daily-rotation">Yes</a>', page)
        self.assertIn("## Honey tree", page)
        self.assertIn("**Common:**", page)
        self.assertIn("**Uncommon:**", page)
        self.assertIn("**Rare:**", page)
        self.assertIn("## Trophy Garden daily rotation", page)
        self.assertNotIn("After National Dex", page)
        self.assertIn("## Game Corner prizes", page)
        self.assertIn("[Potion](../items/potion.md)</span> | 17 | 1,000 coins |", page)
        self.assertIn('<a href="#game-corner-prizes">1</a>', page)
        self.assertIn("game corner", catalog["records"][0]["features"])
        self.assertIn(
            "[Togepi](../pokemon/togepi.md)</span> | — |",
            page,
        )

    def test_renders_great_marsh_daily_pool_with_both_dex_groups(self) -> None:
        record = {
            "header_id": 504,
            "internal_name": "GreatMarsh1",
            "location_name_id": 7,
            "name": "Great Marsh",
            "matrix_id": 0,
            "area_data_id": 2,
            "level_script_id": 12,
            "text_archive_id": 433,
            "day_music_id": 1103,
            "night_music_id": 1119,
            "weather_id": 0,
            "camera_id": 3,
            "map_flags": 0,
            "event_file_id": None,
            "encounter_id": None,
            "trainers": [],
            "warps": [],
            "connections": [],
            "daily_encounter_pool": {
                "kind": "great_marsh",
                "species": [{"species_id": 479, "name": "Rotom"}],
                "pre_national_dex_species": [{"species_id": 175, "name": "Togepi"}],
            },
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
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output, references=references)
            page = (output / "header-504.md").read_text(encoding="utf-8")

        self.assertIn("## Great Marsh daily rotation", page)
        self.assertIn("**After National Dex:**", page)
        self.assertIn("**Before National Dex:**", page)
        self.assertIn("[Rotom](../pokemon/rotom.md)", page)
        self.assertIn("[Togepi](../pokemon/togepi.md)", page)
        self.assertIn('<a href="#great-marsh-daily-rotation">Yes</a>', page)


if __name__ == "__main__":
    unittest.main()
