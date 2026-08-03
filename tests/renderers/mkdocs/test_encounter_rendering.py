from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_encounter_pages


class EncounterRenderingTests(unittest.TestCase):
    def test_links_seasonal_and_nonseasonal_gen5_encounters_to_locations(self) -> None:
        seasonal = _encounter_record(8, 3, "spring", "Route 1")
        seasonal["versions"] = ["black"]
        nonseasonal = _encounter_record(9, 4, None, "Dreamyard")
        encounter_dataset = _dataset("encounters", [seasonal, nonseasonal])
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
            seasonal_page = (output / "map-003-spring.md").read_text(
                encoding="utf-8"
            )
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
        "slug": (
            f"map-{map_index:03}-{season}" if season else f"map-{map_index:03}"
        ),
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
