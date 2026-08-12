from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_encounter_pages


class EncounterRenderingTests(unittest.TestCase):
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
            "locations": [],
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
                "format": "hgss",
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

        self.assertIn("## Walking (Morning)", page)
        self.assertIn("## Walking (Night)", page)
        self.assertIn('href="#walking-morning"', page)
        self.assertNotIn('href="#walking"', page)
        self.assertIn("## Rock Smash", page)
        self.assertIn("**Hoenn Sound radio:**", page)
        self.assertNotIn("Unown table ID", page)

    def test_links_seasonal_and_nonseasonal_gen5_encounters_to_locations(self) -> None:
        seasonal = _encounter_record(8, 3, "spring", "Route 1")
        seasonal["versions"] = ["black"]
        summer = _encounter_record(10, 3, "summer", "Route 1")
        summer["versions"] = ["black"]
        same_name = _encounter_record(11, 5, "spring", "Map 005")
        same_name["location_names"] = []
        nonseasonal = _encounter_record(9, 4, None, "Dreamyard")
        encounter_dataset = _dataset(
            "encounters", [seasonal, summer, same_name, nonseasonal]
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
            render_encounter_pages(
                encounter_dataset,
                output,
                relationships=relationships,
            )
            seasonal_page = (output / "map-003-spring.md").read_text(encoding="utf-8")
            nonseasonal_page = (output / "map-004.md").read_text(encoding="utf-8")

        self.assertIn("## Map headers", seasonal_page)
        self.assertIn('<a href="#map-headers">2</a>', seasonal_page)
        self.assertIn(
            "| [Route 1](../locations/header-006.md) | 6 | Black |",
            seasonal_page,
        )
        self.assertIn(
            "| [Route 1](../locations/header-007.md) | 7 | Black |",
            seasonal_page,
        )
        self.assertIn("## Same-name encounter areas", seasonal_page)
        self.assertIn("| 3 | Summer | Seasonal variant |", seasonal_page)
        self.assertIn("[Map 003 (Summer)](map-003-summer.md)", seasonal_page)
        self.assertIn("| 5 | Spring | Same display name |", seasonal_page)
        self.assertIn("[Map 005 (Spring)](map-005-spring.md)", seasonal_page)
        self.assertIn("## Map headers", nonseasonal_page)
        self.assertIn(
            "| [Dreamyard](../locations/header-008.md) | 8 | White |",
            nonseasonal_page,
        )

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
            page = (output / "map-003-spring.md").read_text(encoding="utf-8")

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
            page = (output / "map-002-spring.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("# Icirrus City", page)
        self.assertNotIn("# Map 002", page)
        self.assertEqual(page.count("gastrodon"), 2)
        self.assertIn("| 45–55 | 20% |", page)
        self.assertIn("| 55–65 | 80% |", page)
        self.assertEqual(catalog["records"][0]["label"], "Icirrus City")
        self.assertEqual(catalog["records"][0]["locations"], ["Icirrus City"])


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


if __name__ == "__main__":
    unittest.main()
