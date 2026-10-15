from __future__ import annotations

import unittest

from romwiki.engines.gen4.platinum import parse_encounter_record
from romwiki.engines.gen5.bw import parse_encounter_entry
from romwiki.pipeline.enrichment.encounters import enrich_encounter_dataset
from romwiki.sources import PokeDBGeneration


class EncounterEnrichmentTests(unittest.TestCase):
    def test_enriches_species_for_active_areas(self) -> None:
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
                "engine": "gen4_platinum",
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            pokedb,
        )

        self.assertEqual(enriched["active_record_count"], 1)
        self.assertEqual(enriched["encounter_format"], "conditional")
        pokemon = enriched["records"][0]["walking"]["slots"][0]["pokemon"]
        self.assertEqual(pokemon["name"], "Bulbasaur")

    def test_marks_timed_walking_special_encounters_by_shape(self) -> None:
        empty_method = {"rate": 0, "slots": []}
        source = {
            "area_id": 0,
            "walking_rate": 0,
            "walking_variants": {"morning": [], "day": [], "night": []},
            "surf": empty_method,
            "rock_smash": empty_method,
            "old_rod": empty_method,
            "good_rod": empty_method,
            "super_rod": empty_method,
            "swarm_species_ids": [0, 0],
            "radio_species_ids": [0, 0, 0, 0],
            "night_fishing_species_id": 0,
            "fishing_swarm_species_id": 0,
            "provenance": {"archive": "encounters.narc", "member": 0},
        }

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "engine": "gen4_hgss",
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            PokeDBGeneration(
                pokemon_by_id={},
                pokemon_by_name={},
                pokemon_by_species={},
                abilities_by_id={},
                items_by_id={},
            ),
        )

        record = enriched["records"][0]
        self.assertEqual(record["special"]["format"], "direct-species")
        self.assertEqual(set(record["walking_variants"]), {"morning", "day", "night"})


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

    def test_enriches_species_for_an_active_area(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
