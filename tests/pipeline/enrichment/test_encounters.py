from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from romwiki.engines.gen4.dppt import parse_encounter_record
from romwiki.engines.gen5.bw import parse_encounter_entry
from romwiki.pipeline.enrichment.encounters import enrich_encounter_dataset
from romwiki.renderers.mkdocs import render_encounter_pages
from romwiki.sources import PokeDBGeneration


class EncounterEnrichmentTests(unittest.TestCase):
    def test_enriches_species_and_renders_active_areas(self) -> None:
        data = bytearray(424)
        data[0:4] = (30).to_bytes(4, "little")
        data[4:8] = (5).to_bytes(4, "little")
        data[8:12] = (1).to_bytes(4, "little")
        data[0x64:0x68] = (2).to_bytes(4, "little")  # swarm_species_ids[0]
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
            pokemon_by_id={
                1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"},
                2: {"id": 2, "name": "ivysaur", "species": "ivysaur"},
            },
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            pokedb,
        )

        self.assertEqual(enriched["active_record_count"], 1)
        pokemon = enriched["records"][0]["walking"]["slots"][0]["pokemon"]
        self.assertEqual(pokemon["name"], "Bulbasaur")
        enriched["records"][0]["special"]["radar"][0] = {
            "id": 4,
            "name": "Charmander",
            "slug": "charmander",
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "area-099.md"
            stale_page.parent.mkdir(parents=True, exist_ok=True)
            stale_page.write_text("stale", encoding="utf-8")
            count = render_encounter_pages(enriched, output)
            page = (output / "area-000.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertFalse(stale_page.exists())
        self.assertIn("# Route 201", page)
        self.assertIn(
            "| [Route 201](../locations/header-010.md) | `header-010` | 16 | `W201` |",
            page,
        )
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn("**Swarm:**", page)
        self.assertIn("[Ivysaur](../pokemon/ivysaur.md)", page)
        # Swarm replaces walking slot 0's species only, so it inherits that
        # slot's level (5) and fixed chance (20%).
        self.assertIn("| 5 | 20% |", page)
        self.assertEqual(catalog["kind"], "encounters")
        self.assertEqual(catalog["records"][0]["route_id"], "area-000")
        self.assertIn("Ivysaur", catalog["records"][0]["pokemon"])
        self.assertIn("ivysaur", catalog["records"][0]["search_text"])
        self.assertEqual(catalog["records"][0]["methods"], ["walking"])
        self.assertIn("Charmander", catalog["records"][0]["pokemon"])
        self.assertIn("Charmander", catalog["records"][0]["method_pokemon"]["walking"])
        self.assertIn("charmander", catalog["records"][0]["search_text"])
        self.assertIn(
            {
                "kind": "pokemon",
                "id": 4,
                "label": "Charmander",
                "url": "../pokemon/charmander/",
            },
            catalog["records"][0]["pokemon_refs"],
        )

    def test_only_pages_skips_detail_pages_but_keeps_full_catalog(self) -> None:
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
                "engine": "gen4_dppt",
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            pokedb,
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_encounter_pages(enriched, output, only_pages=frozenset())
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 0)
        self.assertFalse((output / "area-000.md").exists())
        self.assertEqual(len(catalog["records"]), 1)


class Gen5EncounterEnrichmentTests(unittest.TestCase):
    def test_resolves_wild_forms_without_treating_unknown_operands_as_forms(
        self,
    ) -> None:
        data = bytearray(232)
        data[0] = 20
        for slot_index in range(12):
            base = 8 + slot_index * 4
            species_id = 550 if slot_index == 0 else 1
            form_id = 1
            data[base : base + 2] = (species_id | form_id << 11).to_bytes(2, "little")
            data[base + 2] = 10
            data[base + 3] = 10
        (area,) = parse_encounter_entry(
            bytes(data), map_index=0, archive_path="wild_pokemon.narc"
        )
        pokedb = PokeDBGeneration(
            pokemon_by_id={
                1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"},
                550: {
                    "id": 550,
                    "name": "basculin-red-striped",
                    "species": "basculin",
                },
            },
            pokemon_by_name={
                "basculin-blue-striped": {
                    "id": 10016,
                    "name": "basculin-blue-striped",
                    "species": "basculin",
                }
            },
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "engine": "gen5_b2w2",
                "source": {"archive": "wild_pokemon.narc"},
                "records": [area.to_dict()],
            },
            pokedb,
        )

        slots = enriched["records"][0]["grass_cave"]["slots"]
        self.assertEqual(slots[0]["pokemon"]["slug"], "basculin-blue-striped")
        self.assertEqual(slots[0]["pokemon"]["name"], "Basculin Blue Striped")
        self.assertEqual(slots[1]["pokemon"]["slug"], "bulbasaur")
        self.assertEqual(slots[1]["pokemon"]["name"], "Bulbasaur")

    def test_enriches_species_and_renders_an_active_area(self) -> None:
        data = bytearray(232)
        data[0] = 20  # grass_cave rate
        # A nonzero rate requires every one of grass_cave's 12 slots to hold
        # a valid species ID (cursor = offset(0) + 8, 4 bytes per slot).
        for slot_index in range(12):
            base = 8 + slot_index * 4
            data[base : base + 2] = (1).to_bytes(2, "little")  # species 1, form 0
            data[base + 2] = 3
            data[base + 3] = 5
        (area,) = parse_encounter_entry(
            bytes(data), map_index=0, archive_path="wild_pokemon.narc"
        )
        source = area.to_dict()
        source["location_names"] = ["Route 1"]
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
                "engine": "gen5_bw",
                "source": {"archive": "wild_pokemon.narc"},
                "records": [source],
            },
            pokedb,
        )

        self.assertEqual(enriched["active_record_count"], 1)
        record = enriched["records"][0]
        self.assertEqual(record["name"], "Route 1")
        self.assertEqual(record["slug"], "map-000")
        slot = record["grass_cave"]["slots"][0]
        self.assertEqual(slot["pokemon"]["name"], "Bulbasaur")
        self.assertEqual(slot["minimum_level"], 3)
        self.assertEqual(slot["maximum_level"], 3)
        self.assertFalse(record["doubles_grass"]["rate"])

        comparison = {
            "baseline": "black-us",
            "records": [
                {
                    "kind": "wild_encounters",
                    "key": 0,
                    "status": "changed",
                    "changes": [
                        {
                            "field": "grass_cave",
                            "label": "Grass/Cave",
                            "before": {"rate": 20, "slots": []},
                            "after": record["grass_cave"],
                        }
                    ],
                }
            ],
        }
        blaze_record = deepcopy(record)
        volt_record = deepcopy(record)
        for slot in volt_record["grass_cave"]["slots"]:
            slot["pokemon"] = {
                "id": 2,
                "name": "Ivysaur",
                "slug": "ivysaur",
            }
        record["version_variants"] = {
            "blaze-black": blaze_record,
            "volt-white": volt_record,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_encounter_pages(enriched, output, comparison)
            page = (output / "map-000.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Route 1", page)
        self.assertIn("Grass/Cave", page)
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn('=== "Blaze Black"', page)
        self.assertIn('=== "Volt White"', page)
        self.assertIn("[Ivysaur](../pokemon/ivysaur.md)", page)
        self.assertIn("## Hack changes", page)
        self.assertEqual(catalog["kind"], "encounters")
        self.assertEqual(catalog["records"][0]["route_id"], "map-000")
        self.assertEqual(catalog["records"][0]["methods"], ["Grass/Cave"])
        self.assertIn("Bulbasaur", catalog["records"][0]["pokemon"])
        self.assertIn("Ivysaur", catalog["records"][0]["pokemon"])
        self.assertEqual(catalog["records"][0]["change_status"], "changed")


if __name__ == "__main__":
    unittest.main()
