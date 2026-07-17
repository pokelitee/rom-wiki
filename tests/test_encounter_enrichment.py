from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.engines.gen4_dppt import parse_encounter_record
from romwiki.pipeline.enrich import enrich_encounter_dataset
from romwiki.renderers.mkdocs import render_encounter_pages
from romwiki.sources import PokeDBGeneration


class EncounterEnrichmentTests(unittest.TestCase):
    def test_enriches_species_and_renders_active_areas(self) -> None:
        data = bytearray(424)
        data[0:4] = (30).to_bytes(4, "little")
        data[4:8] = (5).to_bytes(4, "little")
        data[8:12] = (1).to_bytes(4, "little")
        source = parse_encounter_record(
            bytes(data), area_id=0, archive_path="encounters.narc"
        ).to_dict()
        source["locations"] = [
            {
                "header_id": 10,
                "internal_name": "W201",
                "location_name_id": 16,
                "name": "Route 201",
            }
        ]
        pokedb = PokeDBGeneration(
            pokemon_by_id={1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            pokedb,
        )

        self.assertEqual(enriched["active_record_count"], 1)
        pokemon = enriched["records"][0]["walking"]["slots"][0]["pokemon"]
        self.assertEqual(pokemon["name"], "Bulbasaur")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_encounter_pages(enriched, output)
            page = (output / "area-000.md").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("# Route 201", page)
        self.assertIn(
            "| [10](../locations/header-010.md) | Route 201 | `W201` |", page
        )
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)


if __name__ == "__main__":
    unittest.main()
