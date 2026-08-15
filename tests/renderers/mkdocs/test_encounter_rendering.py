from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_encounter_pages
from romwiki.renderers.mkdocs.encounters import _season_version_tabs


class EncounterRenderingTests(unittest.TestCase):
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
