from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_location_pages
from romwiki.renderers.mkdocs.references import ReferenceIndex


class LocationRenderingTests(unittest.TestCase):
    def test_renders_encounter_map_hack_changes_immediately_before_provenance(
        self,
    ) -> None:
        record = {
            "header_id": 6,
            "name": "Route 1",
            "encounter_map_index": None,
            "matrix_id": 1,
            "provenance": {"archive": "a/0/1/2", "member": 6},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        dataset = {"game": "test", "engine": "gen5_bw", "records": [record]}
        comparison = {
            "baseline": "black-us",
            "records": [
                {
                    "key": 6,
                    "status": "changed",
                    "changes": [{"label": "Matrix ID", "before": 0, "after": 1}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output, comparison=comparison)
            page = (output / "header-006.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        provenance_divider = page.index("\n---\n\n<details")
        self.assertLess(page.index("## Hack changes"), provenance_divider)
        self.assertLess(provenance_divider, page.index("Data provenance"))
        self.assertEqual(catalog["records"][0]["change_status"], "changed")

    def test_links_hgss_location_to_nonseasonal_encounter_area(self) -> None:
        record = {
            "header_id": 7,
            "name": "Route 29",
            "encounter_map_index": 28,
            "matrix_id": 0,
            "provenance": {"archive": "arm9", "member": 7},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        dataset = {
            "game": "heartgold-us",
            "engine": "gen4_hgss",
            "records": [record],
        }
        relationships = build_relationship_index(
            {
                "locations": dataset,
                "encounters": {
                    "game": "heartgold-us",
                    "records": [{"area_id": 28, "name": "Route 29"}],
                },
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output, relationships=relationships)
            page = (output / "header-007.md").read_text(encoding="utf-8")

        self.assertIn(
            "[Route 29](../encounters/area-028.md)",
            page,
        )

    def test_links_headbutt_encounters_and_combines_comparisons(self) -> None:
        location = {
            "header_id": 9,
            "name": "Route 1",
            "encounter_map_index": 3,
            "matrix_id": 0,
            "provenance": {"archive": "arm9", "member": 9},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        pokemon = {"id": 163, "slug": "hoothoot", "name": "Hoothoot"}
        ordinary = {
            "area_id": 111,
            "map_index": 3,
            "name": "Route 1",
            "active": True,
        }
        headbutt = {
            "area_id": 142,
            "source_type": "headbutt",
            "header_id": 9,
            "name": "Route 1",
            "active": True,
            "location": {"header_id": 9, "name": "Route 1"},
            "pools": {
                "common": [
                    {
                        "species_id": 163,
                        "minimum_level": 2,
                        "maximum_level": 3,
                        "chance": 50,
                        "pokemon": pokemon,
                    }
                ],
                "rare": [],
                "secret": [],
            },
            "tree_groups": [{"group": 0, "kind": "regular", "coordinates": [[4, 8]]}],
            "provenance": {"archive": "a/2/5/2", "member": 9},
        }
        dataset = {
            "game": "heartgold-us",
            "engine": "gen4_hgss",
            "records": [location],
        }
        relationships = build_relationship_index(
            {
                "locations": dataset,
                "encounters": {
                    "game": "heartgold-us",
                    "records": [ordinary, headbutt],
                },
            }
        )
        location_comparison = {
            "baseline": "heartgold-us",
            "records": [{"key": 9, "status": "unchanged", "changes": []}],
        }
        encounter_comparison = {
            "baseline": "heartgold-us",
            "records": [
                {
                    "key": "headbutt-009",
                    "status": "unchanged",
                    "changes": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(
                dataset,
                output,
                comparison=location_comparison,
                relationships=relationships,
                encounter_comparison=encounter_comparison,
            )
            page = (output / "header-009.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        # The full Headbutt table now lives on its own encounters/ page; the
        # location page only links to it.
        self.assertIn(
            "[Headbutt encounters — Route 1](../encounters/headbutt-009.md)", page
        )
        # The ordinary and conditional encounter rows must share a single
        # table under "## Wild encounters" rather than stacking two.
        self.assertEqual(page.count("| Seasons | Encounter area | Version |"), 1)
        self.assertIn("[Route 1](../encounters/map-003.md)", page)
        self.assertNotIn("[Hoothoot](../pokemon/hoothoot.md)", page)
        self.assertEqual(page.count("## Hack changes"), 1)
        self.assertIn("**Location**", page)
        self.assertIn("**Headbutt encounters — Route 1**", page)
        self.assertNotIn("### Location\n", page)
        self.assertLess(page.index("## Hack changes"), page.index("Data provenance"))
        self.assertIn('<a href="#wild-encounters">Yes</a>', page)
        self.assertIn("headbutt encounters", catalog["records"][0]["features"])
        self.assertEqual(
            catalog["records"][0]["feature_anchors"]["headbutt encounters"],
            "wild-encounters",
        )

    def test_links_hidden_grotto_and_daily_swarm(self) -> None:
        # Despite gen5_b2w2's Gen4-DPPt-flavored event/matrix data, its
        # `formats.locations` is "encounter-map", so this renders through
        # location_encounter_map.py -- not location_event_map.py, which never
        # sees conditional encounters (see location_features.py's
        # event_map_feature_rows docstring).
        location = {
            "header_id": 445,
            "internal_name": "map_445",
            "location_name_id": 7,
            "name": "Floccesy Ranch",
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
            "encounter_map_index": None,
            "items": [],
            "shops": [],
            "pokemon_gifts": [],
            "npc_trades": [],
            "static_encounters": [],
            "roaming_activations": [],
            "trainers": [],
            "warps": [],
            "connections": [],
            "provenance": {"archive": "a/0/1/2", "member": 445},
        }
        pokemon = {
            "id": 206,
            "slug": "dunsparce",
            "name": "Dunsparce",
            "sprite": None,
        }
        common = {
            "active": True,
            "location": {"header_id": 445, "name": "Floccesy Ranch"},
        }
        grotto = {
            **common,
            "area_id": 174,
            "source_type": "hidden-grotto",
            "grotto_id": 0,
            "name": "Floccesy Ranch",
            "pokemon": [
                {
                    "species_id": 206,
                    "minimum_level": 10,
                    "maximum_level": 15,
                    "female_percentage": 30,
                    "pool_chance": 1,
                    "group": 0,
                    "pokemon": pokemon,
                }
            ],
            "visible_items": [
                {
                    "item_id": 82,
                    "pool_chance": 1,
                    "group": 0,
                    "item": {"id": 82, "slug": "fire-stone", "name": "Fire Stone"},
                }
            ],
            "hidden_items": [],
            "provenance": {"archive": "a/2/7/3", "member": 0},
        }
        swarm = {
            **common,
            "area_id": 194,
            "source_type": "daily-swarm",
            "header_id": 445,
            "name": "Floccesy Ranch",
            "species_id": 206,
            "minimum_level": 40,
            "maximum_level": 55,
            "table_offset": 0x50C0C,
            "pokemon": pokemon,
            "provenance": {"archive": "overlay36", "member": 2},
        }
        dataset = {"game": "test", "engine": "gen5_b2w2", "records": [location]}
        relationships = build_relationship_index(
            {
                "locations": dataset,
                "encounters": {"game": "test", "records": [grotto, swarm]},
            }
        )
        references = ReferenceIndex.from_datasets(
            {
                "items": {
                    "records": [
                        {
                            "item_id": 82,
                            "name": "Fire Stone",
                            "slug": "fire-stone",
                            "reference": {
                                "sprite_url": "https://example.test/fire-stone.png"
                            },
                        }
                    ]
                }
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(
                dataset,
                output,
                references=references,
                relationships=relationships,
            )
            page = (output / "header-445.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        # The full tables now live on their own encounters/ pages; the
        # location page only links to them.
        self.assertIn(
            "[Hidden Grotto 00 — Floccesy Ranch](../encounters/hidden-grotto-00.md)",
            page,
        )
        self.assertIn(
            "[Daily Swarm — Floccesy Ranch](../encounters/daily-swarm-445.md)", page
        )
        # Both conditional rows must share a single table under
        # "## Wild encounters" rather than stacking one per source.
        self.assertEqual(page.count("| Seasons | Encounter area | Version |"), 1)
        self.assertNotIn("[Fire Stone](../items/fire-stone.md)", page)
        self.assertNotIn("40–55", page)
        self.assertNotIn("header-445.md#daily-swarm", page)
        self.assertIn('<a href="#wild-encounters">1</a>', page)
        self.assertIn('<a href="#wild-encounters">Yes</a>', page)
        entry = catalog["records"][0]
        self.assertIn("hidden grotto", entry["features"])
        self.assertIn("daily swarm", entry["features"])
        self.assertEqual(entry["feature_anchors"]["hidden grotto"], "wild-encounters")
        self.assertEqual(entry["feature_anchors"]["daily swarm"], "wild-encounters")

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

        self.assertEqual(page.count("[Route 1](../encounters/map-003.md)"), 1)
        self.assertIn("| Spring / Summer |", page)
        self.assertIn("| Black / White |", page)
        self.assertIn("Wild encounter table index | `3`", page)
        self.assertIn(
            "[Dreamyard](../encounters/map-004.md)",
            nonseasonal_page,
        )
        self.assertNotIn("| Season |", nonseasonal_page)

    def test_omits_an_unresolved_gen5_encounter_reference(self) -> None:
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
        dataset = {
            "game": "test",
            "engine": "gen5_bw",
            "records": [record],
        }
        relationships = build_relationship_index({"locations": dataset})

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output, relationships=relationships)
            page = (output / "header-006.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertNotIn("## Wild encounters", page)
        self.assertNotIn("No rendered encounter-area variant", page)
        self.assertEqual(catalog["records"][0]["route_id"], "header-006")
        self.assertNotIn("encounters", catalog["records"][0]["features"])

    def test_keeps_duplicate_gen5_location_labels_clean(self) -> None:
        base = {
            "name": "Route 1",
            "encounter_map_index": None,
            "matrix_id": 0,
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        dataset = {
            "engine": "gen5_bw",
            "records": [
                {
                    **base,
                    "header_id": 6,
                    "provenance": {"archive": "a/0/1/2", "member": 6},
                },
                {
                    **base,
                    "header_id": 7,
                    "provenance": {"archive": "a/0/1/2", "member": 7},
                },
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            first_page = (output / "header-006.md").read_text(encoding="utf-8")
            second_page = (output / "header-007.md").read_text(encoding="utf-8")

        self.assertEqual(
            [(record["label"], record["route_id"]) for record in catalog["records"]],
            [("Route 1", "header-006"), ("Route 1", "header-007")],
        )
        self.assertTrue(
            all("(header " not in record["label"] for record in catalog["records"])
        )
        self.assertIn("## Same-name locations", first_page)
        self.assertIn("[Route 1](header-007.md) | — | `header-007` | — |", first_page)
        self.assertIn("[Route 1](header-006.md) | — | `header-006` | — |", second_page)
        self.assertIn("may represent different rooms or map sections", first_page)

    def test_renders_only_explicit_profile_section_names(self) -> None:
        base = {
            "name": "Chargestone Cave",
            "encounter_map_index": None,
            "matrix_id": 0,
            "internal_name": None,
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "shops": [],
        }
        dataset = {
            "engine": "gen5_bw",
            "records": [
                {
                    **base,
                    "header_id": 61,
                    "section_name": "Chargestone Cave B1F",
                    "section_name_source": {
                        "source": "profile",
                        "profile": "example-hack",
                        "key": "header-061",
                    },
                    "provenance": {"archive": "a/0/1/2", "member": 61},
                },
                {
                    **base,
                    "header_id": 62,
                    "section_name": None,
                    "section_name_source": None,
                    "provenance": {"archive": "a/0/1/2", "member": 62},
                },
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            resolved = (output / "header-061.md").read_text(encoding="utf-8")
            unresolved = (output / "header-062.md").read_text(encoding="utf-8")

        self.assertEqual(catalog["records"][0]["label"], "Chargestone Cave")
        self.assertEqual(catalog["records"][1]["label"], "Chargestone Cave")
        self.assertEqual(catalog["records"][1]["location_name"], "Chargestone Cave")
        self.assertEqual(catalog["records"][1]["section_name"], "Chargestone Cave B1F")
        self.assertIn("# Chargestone Cave", resolved)
        self.assertIn("<dt>Location</dt><dd>Chargestone Cave</dd>", resolved)
        self.assertIn("<dt>Section</dt><dd>Chargestone Cave B1F</dd>", resolved)
        self.assertIn("profile `example-hack`, key `header-061`", resolved)
        self.assertIn("# Chargestone Cave", unresolved)
        self.assertNotIn("<dt>Section</dt>", unresolved)

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
        self.assertEqual(catalog["records"][0]["feature_anchors"]["shops"], "shops")

    def test_renders_special_vendor_currency_and_runtime_availability(self) -> None:
        record = {
            "header_id": 67,
            "name": "Gear Station",
            "encounter_map_index": None,
            "matrix_id": 0,
            "provenance": {"archive": "a/0/1/2", "member": 67},
            "trainers": [],
            "warps": [],
            "static_encounters": [],
            "connections": [],
            "items": [],
            "npc_trades": [
                {
                    "trade_id": 0,
                    "requested_species_id": 546,
                    "requested_species_name": "Cottonee",
                    "offered_species_id": 548,
                    "offered_species_name": "Petilil",
                    "nickname": "Lillil",
                    "held_item_id": None,
                    "held_item_name": None,
                    "ivs": [20, 20, 20, 20, 20, 20],
                    "contest_stats": [0, 0, 0, 0, 0],
                    "ot_id": 39922,
                    "ot_name": "Lina",
                    "versions": ["black"],
                }
            ],
            "shops": [
                {
                    "kind": "exchange",
                    "currency": "bp",
                    "inventory_id": None,
                    "items": [
                        {
                            "item_id": 350,
                            "name": "TM23",
                            "price": 36,
                            "required_badges": None,
                        }
                    ],
                    "name": "Battle Point TM exchange",
                    "is_main_game": True,
                    "dynamic": False,
                },
                {
                    "kind": "market",
                    "currency": "money",
                    "inventory_id": None,
                    "items": [
                        {
                            "item_id": 80,
                            "name": "Sun Stone",
                            "price": 10000,
                            "required_badges": None,
                            "availability": "Current resident: Lena",
                        }
                    ],
                    "name": "Black City resident market",
                    "is_main_game": False,
                    "dynamic": False,
                    "availability": "Post-game; the market appears with 4 residents.",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_location_pages({"engine": "gen5_bw", "records": [record]}, output)
            page = (output / "header-067.md").read_text(encoding="utf-8")

        self.assertIn("### Battle Point TM exchange", page)
        self.assertIn("| 350 | 36 BP | Main game |", page)
        self.assertIn("the market appears with 4 residents", page)
        self.assertIn("| 80 | ₽10,000 | Current resident: Lena |", page)
        self.assertIn("## In-game trades", page)
        self.assertIn("| Black |", page)

    @staticmethod
    def _render_feature_rich_location(
        npc_trades: list[dict[str, Any]] | None = None,
    ) -> tuple[int, bool, str, dict]:
        record = {
            "header_id": 45,
            "internal_name": "C03",
            "location_name_id": 7,
            "name": "Oreburgh City",
            "section_name": "Oreburgh City central district",
            "section_name_source": {
                "source": "profile",
                "profile": "example-platinum-hack",
                "key": "C03",
            },
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
                    "destination_section_name": "Oreburgh Gym",
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
        if npc_trades is not None:
            record["npc_trades"] = npc_trades
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
        relationships = build_relationship_index(
            {
                "locations": {
                    "game": "test",
                    "records": [
                        {
                            "header_id": 47,
                            "name": "Oreburgh City",
                            "section_name": "Oreburgh Gym",
                        },
                        {
                            "header_id": 344,
                            "name": "Route 203",
                            "section_name": "Route 203 west",
                        },
                    ],
                }
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "header-999.md"
            stale_page.parent.mkdir(parents=True, exist_ok=True)
            stale_page.write_text("stale", encoding="utf-8")

            count = render_location_pages(
                dataset,
                output,
                references=references,
                relationships=relationships,
            )
            page = (output / "header-045.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            stale_page_removed = not stale_page.exists()

        return count, stale_page_removed, page, catalog

    def test_renders_location_summary_and_catalog(self) -> None:
        count, stale_page_removed, page, catalog = self._render_feature_rich_location()

        self.assertEqual(count, 1)
        self.assertTrue(stale_page_removed)
        self.assertIn("# Oreburgh City", page)
        self.assertIn("<dt>Location</dt><dd>Oreburgh City</dd>", page)
        self.assertIn("profile `example-platinum-hack`, key `C03`", page)
        self.assertEqual(catalog["records"][0]["location_name"], "Oreburgh City")
        self.assertEqual(
            catalog["records"][0]["section_name"],
            "Oreburgh City central district",
        )
        self.assertIn("../encounters/area-003.md", page)
        self.assertIn('<a href="#wild-encounters">Yes</a>', page)
        self.assertIn('<a href="#item-pickups">2</a>', page)
        self.assertIn('<a href="#shops">2</a>', page)
        self.assertNotIn("In-game trades", page)
        self.assertIn("../trainers/trainer-0246.md", page)
        self.assertEqual(catalog["kind"], "locations")
        self.assertIn("shops", catalog["records"][0]["features"])
        self.assertEqual(catalog["records"][0]["feature_anchors"]["shops"], "shops")
        self.assertEqual(
            catalog["records"][0]["feature_anchors"]["encounters"],
            "wild-encounters",
        )

    def test_formats_npc_trade_unused_values_as_a_plain_list(self) -> None:
        trade = {
            "trade_id": 3,
            "requested_species_id": 175,
            "requested_species_name": "Togepi",
            "offered_species_id": 479,
            "offered_species_name": "Rotom",
            "nickname": "Volty",
            "held_item_id": None,
            "held_item_name": None,
            "ivs": [20, 20, 20, 20, 20, 20],
            "contest_stats": [0, 0, 0, 0, 0],
            "ot_id": 1234,
            "ot_name": "Mira",
            "versions": ["platinum"],
            "personality": 0x1234ABCD,
            "unused_values": (0, 65535),
        }

        _, _, page, _ = self._render_feature_rich_location(npc_trades=[trade])

        self.assertIn(
            "Trade `3` (Volty) personality value: `0x1234ABCD`, "
            "unused record values: `[0, 65535]`.",
            page,
        )

    def test_renders_location_items_shops_and_encounters(self) -> None:
        _, _, page, _ = self._render_feature_rich_location()

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
        self.assertIn("## Game Corner prizes", page)
        self.assertIn("[Potion](../items/potion.md)</span> | 17 | 1,000 coins |", page)
        self.assertIn('<a href="#game-corner-prizes">1</a>', page)
        self.assertIn(
            "[Togepi](../pokemon/togepi.md)</span> | — |",
            page,
        )

    def test_renders_location_navigation_and_map_metadata(self) -> None:
        _, _, page, _ = self._render_feature_rich_location()

        self.assertIn("header-047.md", page)
        self.assertIn(
            "| Warp | Position | To | Section | Map ID | Arrival |",
            page,
        )
        self.assertIn(
            "[Oreburgh City](header-047.md) | Oreburgh Gym | `header-047` | 0 |",
            page,
        )
        self.assertNotIn("C03GYM0101", page.split("## Outdoor connections")[0])
        self.assertIn("header-344.md", page)
        self.assertIn("[Route 203](header-344.md)", page)
        self.assertIn("| Direction | To | Map ID |", page)
        self.assertIn("## Roaming activations", page)
        self.assertIn("Darkrai", page)
        self.assertIn("| 2 | `51@0x140` |", page)
        self.assertIn("| Music ID | day `1103`, night `1119` |", page)
        self.assertIn("| Weather ID | `0` |", page)
        self.assertIn("| Map flags | `0x0304` |", page)

    def test_renders_location_special_mechanics(self) -> None:
        _, _, page, catalog = self._render_feature_rich_location()

        self.assertIn("roaming", catalog["records"][0]["features"])
        self.assertIn("honey tree", catalog["records"][0]["features"])
        self.assertIn("daily rotation", catalog["records"][0]["features"])
        self.assertIn('<a href="#honey-tree">Yes</a>', page)
        self.assertIn('<a href="#trophy-garden-daily-rotation">Yes</a>', page)
        self.assertIn("## Honey tree", page)
        self.assertIn("### Common", page)
        self.assertIn("### Uncommon", page)
        self.assertIn("### Rare", page)
        self.assertIn("## Trophy Garden daily rotation", page)
        self.assertNotIn("After National Dex", page)
        self.assertIn("game corner", catalog["records"][0]["features"])

    def test_keeps_coordinate_based_destination_warp_in_its_column(self) -> None:
        lines: list[str] = []
        from romwiki.renderers.mkdocs.location_components import append_warps

        append_warps(
            lines,
            [
                {
                    "index": 0,
                    "x": 232,
                    "z": 424,
                    "destination_header_id": 191,
                    "destination_warp_id": None,
                    "destination_name": "PWT",
                    "destination_section_name": None,
                    "destination_internal_name": "map_191",
                    "destination_warp_exists": None,
                    "dynamic": False,
                }
            ],
            "locations/header-001.md",
        )
        page = "\n".join(lines)

        self.assertIn(
            "| 0 | (232, 424) | [PWT](header-191.md) | — | `header-191` | Coordinate-based |",
            page,
        )
        self.assertNotIn("map_191", page)

    def test_explains_dynamic_warp_placeholder_cells(self) -> None:
        lines: list[str] = []
        from romwiki.renderers.mkdocs.location_components import append_warps

        append_warps(
            lines,
            [
                {
                    "index": 0,
                    "x": 488,
                    "z": 824,
                    "destination_header_id": None,
                    "destination_warp_id": None,
                    "destination_name": None,
                    "destination_section_name": None,
                    "destination_internal_name": None,
                    "destination_warp_exists": None,
                    "dynamic": True,
                }
            ],
            "locations/header-150.md",
        )
        page = "\n".join(lines)

        self.assertIn("explicit unavailable values, not missing cells", page)
        self.assertIn("| 0 | (488, 824) | Dynamic destination | — | — | — |", page)

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
        self.assertIn("### After National Dex", page)
        self.assertIn("### Before National Dex", page)
        self.assertIn("[Rotom](../pokemon/rotom.md)", page)
        self.assertIn("[Togepi](../pokemon/togepi.md)", page)
        self.assertIn('<a href="#great-marsh-daily-rotation">Yes</a>', page)


if __name__ == "__main__":
    unittest.main()
