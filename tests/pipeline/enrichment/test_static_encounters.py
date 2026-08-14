from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.pokemon import enrich_personal_dataset
from tests.pipeline.enrichment.test_evolutions import _reference_pokedb
from tests.pipeline.enrichment.test_pokemon import _source_record


class StaticEncounterEnrichmentTests(unittest.TestCase):
    def test_attaches_static_encounters_to_their_species(self) -> None:
        pokedb = _reference_pokedb()
        static_encounters = {
            "game": "test",
            "engine": "gen4_dppt",
            "source": {"archive": "a/0/5/7"},
            "records": [
                {
                    "encounter_id": 0,
                    "species_id": 1,
                    "level": 10,
                    "is_egg": False,
                    "provenance": {"source": "rom", "archive": "a/0/5/7", "member": 0},
                },
                {
                    "encounter_id": 1,
                    "species_id": 1,
                    "level": None,
                    "is_egg": True,
                    "provenance": {"source": "rom", "archive": "a/0/5/7", "member": 1},
                },
            ],
        }

        pokemon = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
            static_encounter_dataset=static_encounters,
        )

        self.assertEqual(
            pokemon["records"][1]["static_encounters"],
            [
                {"level": 10, "is_egg": False},
                {"level": None, "is_egg": True},
            ],
        )
        self.assertEqual(pokemon["records"][2]["static_encounters"], [])
        self.assertEqual(
            pokemon["supplemental_sources"]["static_encounters"],
            {"archive": "a/0/5/7"},
        )

    def test_absent_dataset_leaves_records_with_no_static_encounters(self) -> None:
        pokedb = _reference_pokedb()

        pokemon = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
        )

        self.assertEqual(pokemon["records"][1]["static_encounters"], [])
        self.assertNotIn("supplemental_sources", pokemon)


if __name__ == "__main__":
    unittest.main()
