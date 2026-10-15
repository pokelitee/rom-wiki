from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_encounter_pages
from romwiki.renderers.mkdocs.encounters import (
    _encounter_catalog_url,
    _season_version_tabs,
)
from romwiki.renderers.mkdocs.pokemon import _append_availability
from romwiki.util.errors import SiteError
from romwiki.util.json_io import json_round_trip


class EncounterRenderingTests(unittest.TestCase):
    def test_includes_headbutt_as_its_own_encounter_page(self) -> None:
        dataset = {
            "game": "test",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "records": [
                {
                    "area_id": 142,
                    "source_type": "headbutt",
                    "name": "Route 1",
                    "active": True,
                    "location": {
                        "header_id": 9,
                        "internal_name": "map_009",
                        "name": "Route 1",
                    },
                    "pools": {"common": [], "rare": [], "secret": []},
                    "tree_groups": [],
                    "provenance": {"source": "rom", "archive": "a/2/5/2", "member": 9},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            page = (output / "headbutt-009.md").read_text(encoding="utf-8")

        self.assertEqual(len(catalog["records"]), 1)
        self.assertEqual(catalog["records"][0]["route_id"], "headbutt-009")
        self.assertIn("# Headbutt encounters", page)
        self.assertIn("Route 1", page)
        # Map headers must appear before the encounter tables, the same
        # position ordinary and seasonal encounter pages already use.
        self.assertLess(page.index("## Map headers"), page.index("## Common trees"))

    def test_disambiguates_headbutt_labels_sharing_a_location_name(self) -> None:
        # Two different map headers can share the same display name (a route
        # and a connecting sub-area both named "Route 2", for example), so a
        # bare "Headbutt encounters -- Route 2" label would be identical and
        # indistinguishable for both catalog rows without this.
        def headbutt(area_id: int, header_id: int, internal_name: str) -> dict:
            return {
                "area_id": area_id,
                "source_type": "headbutt",
                "name": "Route 2",
                "active": True,
                "location": {
                    "header_id": header_id,
                    "internal_name": internal_name,
                    "name": "Route 2",
                },
                "pools": {"common": [], "rare": [], "secret": []},
                "tree_groups": [],
                "provenance": {
                    "source": "rom",
                    "archive": "a/2/5/2",
                    "member": area_id,
                },
            }

        dataset = {
            "game": "test",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "records": [
                headbutt(143, 10, "R02"),
                headbutt(199, 414, "R02R0101"),
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            index_page = (output / "index.md").read_text(encoding="utf-8")

        labels = {record["label"] for record in catalog["records"]}
        self.assertEqual(len(labels), 2)
        self.assertIn("Headbutt encounters — Route 2 (R02)", labels)
        self.assertIn("Headbutt encounters — Route 2 (R02R0101)", labels)
        self.assertIn("Headbutt encounters — Route 2 (R02)", index_page)
        self.assertIn("Headbutt encounters — Route 2 (R02R0101)", index_page)

    def test_omits_encounter_areas_with_no_map_header(self) -> None:
        # Some encounter-table entries (Platinum's, in practice) aren't
        # referenced by any map header at all -- leftover/unused ROM data,
        # not a place a player can reach. These shouldn't get a fallback
        # "Encounter Area NNN" page or catalog entry.
        walking_slot = {
            "level": 5,
            "species_id": 25,
            "chance": 100,
            "pokemon": {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None},
        }
        unlinked = {
            "area_id": 60,
            "name": "Encounter Area 060",
            "locations": [],
            "active": True,
            "walking": {"rate": 15, "slots": [walking_slot]},
            "walking_variants": {
                period: {"rate": 15, "slots": [walking_slot]}
                for period in ("morning", "day", "night")
            },
            "special": {
                "format": "direct-species",
                "land_swarm": None,
                "surf_swarm": None,
                "hoenn_radio": [],
                "sinnoh_radio": [],
                "night_fishing": None,
                "fishing_swarm": None,
            },
            "provenance": {"archive": "a/0/1/2", "member": 60},
        }
        linked = {
            "area_id": 61,
            "name": "Route 201",
            "locations": [
                {
                    "header_id": 4,
                    "internal_name": "route201",
                    "name": "Route 201",
                    "location_name_id": 4,
                }
            ],
            "active": True,
            "walking": {"rate": 15, "slots": [walking_slot]},
            "walking_variants": {
                period: {"rate": 15, "slots": [walking_slot]}
                for period in ("morning", "day", "night")
            },
            "special": {
                "format": "direct-species",
                "land_swarm": None,
                "surf_swarm": None,
                "hoenn_radio": [],
                "sinnoh_radio": [],
                "night_fishing": None,
                "fishing_swarm": None,
            },
            "provenance": {"archive": "a/0/1/2", "member": 61},
        }
        dataset = {
            "game": "test",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "encounter_format": "conditional",
            "records": [unlinked, linked],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            index_page = (output / "index.md").read_text(encoding="utf-8")
            written = {path.name for path in output.iterdir()}

        self.assertNotIn("area-060.md", written)
        self.assertIn("area-061.md", written)
        self.assertEqual(len(catalog["records"]), 1)
        self.assertEqual(catalog["records"][0]["id"], 61)
        self.assertNotIn("Encounter Area 060", index_page)
        self.assertIn("Route 201", index_page)

    def test_no_pokemon_links_to_an_unpublished_encounter_area(self) -> None:
        dataset = {
            "game": "test",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "encounter_format": "conditional",
            "records": [
                _walking_area(60, [], 25, "pikachu"),
                _walking_area(
                    61,
                    [
                        {
                            "header_id": 4,
                            "internal_name": "route201",
                            "name": "Route 201",
                            "location_name_id": 4,
                        }
                    ],
                    399,
                    "bidoof",
                ),
            ],
        }
        relationships = build_relationship_index(
            {
                "encounters": dataset,
                "pokemon": {
                    "game": "test",
                    "records": [
                        {"slug": "pikachu", "member": 25, "name": "Pikachu"},
                        {"slug": "bidoof", "member": 399, "name": "Bidoof"},
                    ],
                },
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "encounters"
            render_encounter_pages(dataset, output, relationships=relationships)
            written = {path.name for path in output.iterdir()}
            pages = {}
            for slug, encounters in relationships.pokemon_wild_encounters.items():
                lines: list[str] = []
                _append_availability(lines, encounters, (), f"pokemon/{slug}.md")
                pages[slug] = "\n".join(lines)

        self.assertNotIn("pikachu", relationships.pokemon_wild_encounters)
        self.assertIn("bidoof", relationships.pokemon_wild_encounters)
        linked_pages = {
            target.removeprefix("../encounters/")
            for page in pages.values()
            for target in re.findall(r"\]\((\.\./encounters/[^)#]+)", page)
        }
        self.assertEqual(linked_pages, {"area-061.md"})
        self.assertLessEqual(linked_pages, written)

    def test_raises_a_site_error_for_an_unroutable_catalog_record(self) -> None:
        # A malformed/inconsistent build state (the location engine hasn't
        # registered a route for this area) must surface as the project's
        # own error taxonomy, not a bare ValueError escaping the CLI's
        # RomWikiError boundary as a raw traceback.
        record = _encounter_record(999, 999, None, "Nowhere")
        with (
            patch(
                "romwiki.renderers.mkdocs.encounters.ROUTES.published_href",
                return_value=None,
            ),
            self.assertRaises(SiteError),
        ):
            _encounter_catalog_url(record)

    def test_includes_daily_swarm_as_its_own_encounter_page(self) -> None:
        black = {
            "area_id": 194,
            "source_type": "daily-swarm",
            "header_id": 331,
            "species_id": 311,
            "minimum_level": 40,
            "maximum_level": 55,
            "table_offset": 0x50C0C,
            "name": "Route 6",
            "active": True,
            "location": {
                "header_id": 331,
                "internal_name": "map_331",
                "name": "Route 6",
            },
            "pokemon": {"id": 311, "slug": "plusle", "name": "Plusle"},
            "provenance": {"archive": "overlay36", "member": 2},
        }
        record = {
            **black,
            "versions": ["black-2", "white-2"],
            "version_variants": {
                "black-2": black,
                "white-2": {
                    **black,
                    "species_id": 312,
                    "table_offset": 0x50C00,
                    "pokemon": {"id": 312, "slug": "minun", "name": "Minun"},
                    "provenance": {"archive": "overlay36", "member": 2},
                },
            },
        }
        dataset = {
            "game": "test",
            "engine": "gen5_b2w2",
            "dataset": "wild_encounters",
            "records": [record],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            page = (output / "daily-swarm-331.md").read_text(encoding="utf-8")

        self.assertEqual(len(catalog["records"]), 1)
        self.assertEqual(catalog["records"][0]["route_id"], "daily-swarm-331")
        self.assertIn("# Daily Swarm", page)
        self.assertIn("Plusle", page)
        # Map headers must appear before the encounter table, the same
        # position ordinary and seasonal encounter pages already use.
        self.assertLess(page.index("## Map headers"), page.index("Plusle"))

    def test_includes_hidden_grotto_as_its_own_encounter_page(self) -> None:
        record = {
            "area_id": 174,
            "source_type": "hidden-grotto",
            "grotto_id": 0,
            "name": "Floccesy Ranch",
            "active": True,
            "location": {
                "header_id": 445,
                "internal_name": "map_445",
                "name": "Floccesy Ranch",
            },
            "pokemon": [
                {
                    "species_id": 206,
                    "form_id": 0,
                    "minimum_level": 10,
                    "maximum_level": 15,
                    "female_percentage": 30,
                    "pool_chance": 1,
                    "group": 0,
                    "pokemon": {
                        "id": 206,
                        "slug": "dunsparce",
                        "name": "Dunsparce",
                        "sprite": None,
                    },
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
            "provenance": {"source": "rom", "archive": "a/2/7/3", "member": 0},
        }
        dataset = {
            "game": "test",
            "engine": "gen5_b2w2",
            "dataset": "wild_encounters",
            "records": [record],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            page = (output / "hidden-grotto-00.md").read_text(encoding="utf-8")

        self.assertEqual(len(catalog["records"]), 1)
        self.assertEqual(catalog["records"][0]["route_id"], "hidden-grotto-00")
        self.assertIn("# Hidden Grotto 00", page)
        self.assertIn("Dunsparce", page)
        self.assertIn("Fire Stone", page)
        # Map headers must appear before the encounter tables, the same
        # position ordinary and seasonal encounter pages already use.
        self.assertLess(page.index("## Map headers"), page.index("## Pokémon"))

    def test_nests_versions_inside_season_tabs(self) -> None:
        lines = _season_version_tabs(
            [
                ("black", "spring", ["Black spring"]),
                ("black", "winter", ["Black winter"]),
                ("white", "spring", ["White spring"]),
                ("white", "winter", ["White winter"]),
            ]
        )

        self.assertEqual(lines.count('=== "Spring"'), 1)
        self.assertEqual(lines.count('=== "Winter"'), 1)
        self.assertEqual(lines.count('    === "Black"'), 2)
        self.assertEqual(lines.count('    === "White"'), 2)
        self.assertIn("        Black spring", lines)

    def test_renders_safari_base_and_block_encounters(self) -> None:
        pikachu = {
            "species_id": 25,
            "level": 12,
            "pokemon": {"id": 25, "slug": "pikachu", "name": "Pikachu"},
        }
        eevee = {
            "species_id": 133,
            "level": 18,
            "pokemon": {"id": 133, "slug": "eevee", "name": "Eevee"},
        }
        method = {
            "base_pools": {
                time: [pikachu] * 10 for time in ("morning", "day", "night")
            },
            "block_encounters": [
                {
                    "index": 0,
                    "requirements": [
                        {"block_type": "plains", "count": 3},
                        {"block_type": "forest", "count": 5},
                    ],
                    "times": dict.fromkeys(("morning", "day", "night"), eevee),
                }
            ],
        }
        record = {
            "area_id": 202,
            "source_type": "safari-zone",
            "safari_area_id": 0,
            "area_name": "Plains",
            "name": "Safari Zone — Plains",
            "active": True,
            "locations": [],
            "methods": dict.fromkeys(("grass", "surf"), method),
            "provenance": {"archive": "a/2/3/0", "member": 0},
        }
        dataset = {
            "game": "heartgold-us",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "records": [record],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            index_page = (output / "safari-zone.md").read_text(encoding="utf-8")
            area_page = (output / "safari-zone-00.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("# Safari Zone encounters", index_page)
        self.assertIn("[Plains](safari-zone-00.md)", index_page)
        self.assertIn("# Plains { #plains }", area_page)
        self.assertIn("## Grass", area_page)
        self.assertIn("## Surf", area_page)
        self.assertIn("3 Plains, 5 Forest", area_page)
        self.assertIn("[Eevee](../pokemon/eevee.md) (Lv. 18)", area_page)
        self.assertEqual(catalog["records"][0]["methods"], ["Grass", "Surf"])
        self.assertEqual(
            catalog["records"][0]["method_pokemon"],
            {"Grass": ["Pikachu", "Eevee"], "Surf": ["Pikachu", "Eevee"]},
        )
        self.assertEqual(catalog["records"][0]["url"], "safari-zone-00/")
        # Methods must link to their own-page sections, the same way ordinary
        # and seasonal encounter methods do.
        self.assertEqual(
            catalog["records"][0]["method_anchors"], {"Grass": "grass", "Surf": "surf"}
        )

    def test_links_safari_zone_areas_to_each_other_for_navigation(self) -> None:
        pikachu = {
            "species_id": 25,
            "level": 12,
            "pokemon": {"id": 25, "slug": "pikachu", "name": "Pikachu"},
        }
        method = {
            "base_pools": {time: [pikachu] for time in ("morning", "day", "night")},
            "block_encounters": [],
        }
        plains = {
            "area_id": 202,
            "source_type": "safari-zone",
            "safari_area_id": 0,
            "area_name": "Plains",
            "name": "Safari Zone — Plains",
            "active": True,
            "locations": [],
            "methods": {"grass": method},
            "provenance": {"archive": "a/2/3/0", "member": 0},
        }
        forest = {**plains, "area_id": 203, "safari_area_id": 1, "area_name": "Forest"}
        dataset = {
            "game": "heartgold-us",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "records": [plains, forest],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            plains_page = (output / "safari-zone-00.md").read_text(encoding="utf-8")
            forest_page = (output / "safari-zone-01.md").read_text(encoding="utf-8")

        # Safari area pages must get the same prev/next navigation as the
        # Headbutt/Hidden Grotto/Daily Swarm pages they were the model for.
        self.assertIn('aria-label="Wild encounter navigation"', plains_page)
        self.assertIn('href="../safari-zone-01/"', plains_page)
        self.assertIn(">Forest →</span>", plains_page)
        self.assertIn('aria-label="Wild encounter navigation"', forest_page)
        self.assertIn('href="../safari-zone-00/"', forest_page)
        self.assertIn(">← Plains</span>", forest_page)

    def test_catalog_keeps_pokemon_correlated_with_encounter_methods(self) -> None:
        pikachu = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        eevee = {"id": 133, "slug": "eevee", "name": "Eevee", "sprite": None}
        record = _encounter_record(2, 2, "spring", "Map 002")
        record["grass_cave"] = {
            "rate": 20,
            "slots": [_seasonal_slot(25, 0, 5, 5, 100, pikachu)],
        }
        record["surfing"] = {
            "rate": 10,
            "slots": [_seasonal_slot(133, 0, 15, 20, 100, eevee)],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(_dataset("encounters", [record]), output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        entry = catalog["records"][0]
        self.assertEqual(entry["methods"], ["Grass/Cave", "Surfing"])
        self.assertEqual(
            entry["method_pokemon"],
            {"Grass/Cave": ["Pikachu"], "Surfing": ["Eevee"]},
        )
        self.assertEqual(
            entry["method_anchors"],
            {"Grass/Cave": "grasscave", "Surfing": "surfing"},
        )
        self.assertEqual((entry["min_level"], entry["max_level"]), (5, 20))

    def test_aggregates_nonadjacent_slots_by_species_and_form(self) -> None:
        gastrodon = {
            "id": 423,
            "slug": "gastrodon",
            "name": "Gastrodon",
            "sprite": None,
        }
        shellos = {
            "id": 422,
            "slug": "shellos",
            "name": "Shellos",
            "sprite": None,
        }
        record = _encounter_record(2, 2, "spring", "Map 002")
        record["surfing"] = {
            "rate": 10,
            "slots": [
                _seasonal_slot(423, 0, 45, 55, 20, gastrodon),
                _seasonal_slot(422, 0, 40, 40, 10, shellos),
                _seasonal_slot(423, 1, 50, 60, 30, gastrodon),
                _seasonal_slot(423, 0, 55, 65, 40, gastrodon),
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(_dataset("encounters", [record]), output)
            page = (output / "map-002.md").read_text(encoding="utf-8")

        self.assertIn("| 45–65 | 60% |", page)
        self.assertIn("| 50–60 | 30% |", page)
        self.assertIn("| 40 | 10% |", page)
        self.assertEqual(page.count("[Gastrodon]"), 2)

    def test_aggregates_generation_four_walking_level_envelope(self) -> None:
        pokemon = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        slots = [
            {"species_id": 25, "level": 4, "chance": 20, "pokemon": pokemon},
            {"species_id": 19, "level": 3, "chance": 30, "pokemon": None},
            {"species_id": 25, "level": 8, "chance": 50, "pokemon": pokemon},
        ]
        lines: list[str] = []
        from romwiki.renderers.mkdocs.encounters import _append_walking

        _append_walking(lines, {"rate": 20, "slots": slots}, "encounters/a.md", None)
        page = "\n".join(lines)

        self.assertIn("| 4–8 | 70% |", page)
        self.assertEqual(page.count("[Pikachu]"), 1)

    def test_renders_hgss_periods_rock_smash_and_special_groups(self) -> None:
        pokemon = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        walking_slot = {
            "level": 5,
            "species_id": 25,
            "chance": 100,
            "pokemon": pokemon,
        }
        water_slot = {
            "minimum_level": 5,
            "maximum_level": 7,
            "species_id": 25,
            "chance": 100,
            "pokemon": pokemon,
        }
        empty = {"rate": 0, "slots": []}
        record = {
            "area_id": 0,
            "name": "Route 29",
            "locations": [
                {
                    "header_id": 12,
                    "internal_name": "route29",
                    "name": "Route 29",
                    "location_name_id": 12,
                }
            ],
            "active": True,
            "walking": {"rate": 20, "slots": [walking_slot]},
            "walking_variants": {
                period: {"rate": 20, "slots": [walking_slot]}
                for period in ("morning", "day", "night")
            },
            "surf": empty,
            "rock_smash": {"rate": 5, "slots": [water_slot]},
            "old_rod": empty,
            "good_rod": empty,
            "super_rod": empty,
            "special": {
                "format": "direct-species",
                "land_swarm": pokemon,
                "surf_swarm": None,
                "hoenn_radio": [pokemon],
                "sinnoh_radio": [],
                "night_fishing": None,
                "fishing_swarm": None,
            },
            "provenance": {"archive": "a/0/3/7", "member": 0},
        }
        dataset = {
            "game": "heartgold-us",
            "engine": "gen4_hgss",
            "dataset": "wild_encounters",
            "records": [record],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(dataset, output)
            page = (output / "area-000.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("## Walking (Morning)", page)
        self.assertIn("## Walking (Night)", page)
        self.assertIn('href="#walking-morning"', page)
        self.assertNotIn('href="#walking"', page)
        self.assertIn("## Rock Smash", page)
        self.assertIn("### Hoenn Sound radio", page)
        self.assertNotIn("Unown table ID", page)
        self.assertEqual(
            catalog["records"][0]["method_anchors"],
            {"walking": "walking-morning", "rock smash": "rock-smash"},
        )

    def test_links_seasonal_and_nonseasonal_gen5_encounters_to_locations(self) -> None:
        seasonal = _encounter_record(8, 3, "spring", "Route 1")
        seasonal["versions"] = ["black"]
        summer = _encounter_record(10, 3, "summer", "Route 1")
        summer["versions"] = ["black"]
        autumn = _encounter_record(12, 3, "autumn", "Route 1")
        winter = _encounter_record(13, 3, "winter", "Route 1")
        same_name = _encounter_record(11, 5, "spring", "Map 005")
        same_name["location_names"] = []
        nonseasonal = _encounter_record(9, 4, None, "Dreamyard")
        encounter_dataset = _dataset(
            "encounters", [winter, seasonal, summer, same_name, nonseasonal, autumn]
        )
        location_dataset = _dataset(
            "locations",
            [
                {
                    "header_id": 6,
                    "name": "Route 1",
                    "encounter_map_index": 3,
                },
                {
                    "header_id": 7,
                    "name": "Route 1",
                    "encounter_map_index": 3,
                },
                {
                    "header_id": 8,
                    "name": "Dreamyard",
                    "encounter_map_index": 4,
                    "versions": ["white"],
                },
                {
                    "header_id": 9,
                    "name": "Route 1",
                    "encounter_map_index": 5,
                },
            ],
        )
        relationships = build_relationship_index(
            {"encounters": encounter_dataset, "locations": location_dataset}
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "map-003-spring.md"
            stale_page.write_text("stale", encoding="utf-8")
            render_encounter_pages(
                encounter_dataset,
                output,
                relationships=relationships,
            )
            seasonal_page = (output / "map-003.md").read_text(encoding="utf-8")
            nonseasonal_page = (output / "map-004.md").read_text(encoding="utf-8")
            stale_page_removed = not stale_page.exists()

        self.assertTrue(stale_page_removed)
        self.assertIn("## Map headers", seasonal_page)
        self.assertIn('<a href="#map-headers">2</a>', seasonal_page)
        self.assertIn(
            "| [Route 1](../locations/header-006.md) | — | `header-006` | Black |",
            seasonal_page,
        )
        self.assertIn(
            "| [Route 1](../locations/header-007.md) | — | `header-007` | Black |",
            seasonal_page,
        )
        self.assertIn("## Same-name encounter areas", seasonal_page)
        self.assertIn("[Route 1](map-005.md)", seasonal_page)
        self.assertIn("## Map headers", nonseasonal_page)
        self.assertIn(
            "| [Dreamyard](../locations/header-008.md) | — | `header-008` | White |",
            nonseasonal_page,
        )

    def test_places_season_tabs_around_each_active_pokemon_table(self) -> None:
        pikachu = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        records = []
        for area_id, season in enumerate(("spring", "summer", "autumn", "winter")):
            record = _encounter_record(area_id, 2, season, "Map 002")
            record["grass_cave"] = {
                "rate": 20,
                "slots": [
                    _seasonal_slot(25, 0, 5 + area_id, 7 + area_id, 100, pikachu)
                ],
            }
            record["surfing"] = {
                "rate": 10,
                "slots": [
                    _seasonal_slot(25, 0, 8 + area_id, 9 + area_id, 100, pikachu)
                ],
            }
            records.append(record)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(_dataset("encounters", records), output)
            page = (output / "map-002.md").read_text(encoding="utf-8")

        self.assertEqual(page.count("## Grass/Cave"), 1)
        self.assertEqual(page.count("## Surfing"), 1)
        self.assertEqual(page.count('=== "Spring"'), 2)
        self.assertEqual(page.count('=== "Winter"'), 2)
        self.assertNotIn("    ##", page)
        # The summary card's Methods row must link to its own page section,
        # the same way non-seasonal encounter pages already do.
        self.assertIn('<a href="#grasscave">Grass/Cave</a>', page)
        self.assertIn('<a href="#surfing">Surfing</a>', page)

    def test_combines_version_and_season_in_content_tabs(self) -> None:
        pikachu = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        eevee = {"id": 133, "slug": "eevee", "name": "Eevee", "sprite": None}
        record = _encounter_record(2, 2, "spring", "Map 002")
        black = {**record}
        black["grass_cave"] = {
            "rate": 20,
            "slots": [_seasonal_slot(25, 0, 5, 5, 100, pikachu)],
        }
        white = {**record}
        white["grass_cave"] = {
            "rate": 20,
            "slots": [_seasonal_slot(133, 0, 5, 5, 100, eevee)],
        }
        record["version_variants"] = {"black": black, "white": white}
        comparison = {
            "baseline": "black-white",
            "records": [
                {
                    "key": 2,
                    "status": "changed",
                    "changes": [],
                    "version_comparisons": {
                        version: {
                            "status": "changed",
                            "changes": [
                                {
                                    "label": "Encounter rate",
                                    "before": 10,
                                    "after": 20 if version == "black" else 30,
                                }
                            ],
                        }
                        for version in ("black", "white")
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(
                _dataset("encounters", [record]), output, comparison=comparison
            )
            page = (output / "map-002.md").read_text(encoding="utf-8")

        self.assertEqual(page.count('=== "Black"'), 2)
        self.assertEqual(page.count('=== "White"'), 2)
        self.assertNotIn("· Spring", page)
        self.assertNotIn("**Black**", page)
        self.assertNotIn("**White**", page)
        provenance_divider = page.index("\n---\n\n<details")
        self.assertLess(page.index("## Hack changes"), provenance_divider)

    def test_omits_tabs_for_a_method_unchanged_across_seasons(self) -> None:
        pikachu = {"id": 25, "slug": "pikachu", "name": "Pikachu", "sprite": None}
        records = []
        for area_id, season in enumerate(("spring", "summer", "autumn", "winter")):
            record = _encounter_record(area_id, 2, season, "Map 002")
            record["grass_cave"] = {
                "rate": 20,
                "slots": [_seasonal_slot(25, 0, 5, 7, 100, pikachu)],
            }
            records.append(record)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(_dataset("encounters", records), output)
            page = (output / "map-002.md").read_text(encoding="utf-8")

        self.assertEqual(page.count("## Grass/Cave"), 1)
        self.assertNotIn('=== "Spring"', page)
        self.assertEqual(page.count("[Pikachu]"), 1)

    def test_does_not_guess_an_unresolved_gen5_location_link(self) -> None:
        encounter_dataset = _dataset(
            "encounters", [_encounter_record(8, 3, "spring", "Route 1")]
        )
        relationships = build_relationship_index({"encounters": encounter_dataset})

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(
                encounter_dataset,
                output,
                relationships=relationships,
            )
            page = (output / "map-003.md").read_text(encoding="utf-8")

        self.assertNotIn("## Map headers", page)
        self.assertNotIn("../locations/", page)
        self.assertIn("no location link is guessed", page)

    def test_uses_verified_map_header_name_and_combines_species_rows(self) -> None:
        record = _encounter_record(2, 2, "spring", "Map 002")
        record["location_names"] = []
        pokemon = {
            "id": 423,
            "slug": "gastrodon",
            "name": "Gastrodon",
            "sprite": None,
        }
        record["surfing"] = {
            "rate": 10,
            "slots": [
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 45,
                    "maximum_level": 55,
                    "chance": 20,
                    "pokemon": pokemon,
                },
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 55,
                    "maximum_level": 65,
                    "chance": 10,
                    "pokemon": pokemon,
                },
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 55,
                    "maximum_level": 65,
                    "chance": 10,
                    "pokemon": pokemon,
                },
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 55,
                    "maximum_level": 65,
                    "chance": 10,
                    "pokemon": pokemon,
                },
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 55,
                    "maximum_level": 65,
                    "chance": 10,
                    "pokemon": pokemon,
                },
                {
                    "species_id": 423,
                    "form_id": 0,
                    "minimum_level": 55,
                    "maximum_level": 65,
                    "chance": 40,
                    "pokemon": pokemon,
                },
            ],
        }
        encounter_dataset = _dataset("encounters", [record])
        location_dataset = _dataset(
            "locations",
            [{"header_id": 113, "name": "Icirrus City", "encounter_map_index": 2}],
        )
        relationships = build_relationship_index(
            {"encounters": encounter_dataset, "locations": location_dataset}
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_encounter_pages(
                encounter_dataset,
                output,
                relationships=relationships,
            )
            page = (output / "map-002.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("# Icirrus City", page)
        self.assertNotIn("# Map 002", page)
        self.assertEqual(page.count("gastrodon"), 1)
        self.assertIn("| 45–65 | 100% |", page)
        self.assertEqual(catalog["records"][0]["label"], "Icirrus City")
        self.assertEqual(catalog["records"][0]["locations"], ["Icirrus City"])

    def test_renders_tuple_and_list_raw_values_identically(self) -> None:
        location = {
            "header_id": 3,
            "internal_name": "R201",
            "name": "Route 201",
            "location_name_id": 3,
        }
        record = _walking_area(7, [location], 25, "pikachu")
        del record["walking_variants"]
        record.update(
            special={
                "swarm": [],
                "day": [],
                "night": [],
                "radar": [],
                "unown_forms": [],
                "dual_slot": {},
            },
            bonus_slot_methodology_source="the documented engine weights",
            encounter_form_rates=(0, 0, 0, 0, 0),
            unown_table_id=0,
        )
        dataset = {
            "game": "test",
            "engine": "gen4_platinum",
            "dataset": "wild_encounters",
            "records": [record],
        }

        rendered = []
        for value in (dataset, json_round_trip(dataset)):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                render_encounter_pages(value, output)
                rendered.append(
                    {path.name: path.read_bytes() for path in sorted(output.iterdir())}
                )

        self.assertEqual(rendered[0], rendered[1])
        self.assertIn(
            b"| Encounter form rates | `[0, 0, 0, 0, 0]` |", rendered[0]["area-007.md"]
        )


def _dataset(kind: str, records: list[dict]) -> dict:
    return {
        "game": "test",
        "engine": "gen5_bw",
        "dataset": kind,
        "records": records,
    }


def _encounter_record(
    area_id: int,
    map_index: int,
    season: str | None,
    name: str,
) -> dict:
    empty_method = {"rate": 0, "slots": []}
    return {
        "area_id": area_id,
        "map_index": map_index,
        "season": season,
        "slug": (f"map-{map_index:03}-{season}" if season else f"map-{map_index:03}"),
        "name": name,
        "location_names": [name],
        "active": True,
        "grass_cave": empty_method,
        "doubles_grass": empty_method,
        "shaking_spots": empty_method,
        "surfing": empty_method,
        "surfing_spots": empty_method,
        "fishing": empty_method,
        "fishing_spots": empty_method,
        "provenance": {"archive": "encounters.narc", "member": map_index},
    }


def _walking_area(
    area_id: int, locations: list[dict], species_id: int, slug: str
) -> dict:
    slot = {
        "level": 5,
        "species_id": species_id,
        "chance": 100,
        "pokemon": {"id": species_id, "slug": slug, "name": slug, "sprite": None},
    }
    return {
        "area_id": area_id,
        "name": locations[0]["name"] if locations else f"Encounter Area {area_id:03}",
        "locations": locations,
        "active": True,
        "walking": {"rate": 15, "slots": [slot]},
        "walking_variants": {
            period: {"rate": 15, "slots": [slot]}
            for period in ("morning", "day", "night")
        },
        "special": {
            "format": "direct-species",
            "land_swarm": None,
            "surf_swarm": None,
            "hoenn_radio": [],
            "sinnoh_radio": [],
            "night_fishing": None,
            "fishing_swarm": None,
        },
        "provenance": {"archive": "a/0/1/2", "member": area_id},
    }


def _seasonal_slot(
    species_id: int,
    form_id: int,
    minimum_level: int,
    maximum_level: int,
    chance: int,
    pokemon: dict,
) -> dict:
    return {
        "species_id": species_id,
        "form_id": form_id,
        "minimum_level": minimum_level,
        "maximum_level": maximum_level,
        "chance": chance,
        "pokemon": pokemon,
    }


if __name__ == "__main__":
    unittest.main()
