from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from romwiki.pipeline.enrich import _enrich_trainer, enrich_trainer_dataset
from romwiki.renderers.mkdocs import render_trainer_pages
from romwiki.sources import PokeDBGeneration


class TrainerEnrichmentTests(unittest.TestCase):
    def test_labels_burmy_cosmetic_cloaks(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={
                412: {"id": 412, "name": "burmy", "species": "burmy"}
            },
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "reward_item_ids": [],
            "party": [
                {
                    "species_id": 412,
                    "form_id": 1,
                    "held_item_id": None,
                    "move_ids": [],
                }
            ]
        }

        trainer = _enrich_trainer(source, pokedb, None, None)

        self.assertEqual(
            trainer["party"][0]["pokemon"]["name"], "Burmy (Sandy Cloak)"
        )

    def test_enriches_and_renders_a_trainer_party(self) -> None:
        source = {
            "trainer_id": 0,
            "name": "Tristan",
            "class_id": 2,
            "class_name": "Youngster",
            "has_custom_moves": True,
            "has_held_items": True,
            "unknown_byte": 0,
            "party_count": 1,
            "reward_item_ids": [0, 0, 0, 0],
            "ai_flags": 0,
            "double_battle": False,
            "party": [{
                "difficulty": 0,
                "gender_ability": 0,
                "level": 5,
                "species_id": 1,
                "form_id": 0,
                "held_item_id": 1,
                "move_ids": [33, 0, 0, 0],
                "ball_seal": 0,
            }],
            "trailing_party_data": "",
            "provenance": {"source": "rom", "archive": "trdata.narc", "member": 0},
            "party_provenance": {"source": "rom", "archive": "trpoke.narc", "member": 0},
            "locations": [{
                "header_id": 343,
                "internal_name": "R202",
                "location_name_id": 17,
                "name": "Route 202",
                "event_file_id": 329,
                "object_index": 0,
                "object_local_id": 0,
                "script_id": 3000,
                "trainer_type": 1,
                "x": 181,
                "y": 65536,
                "z": 818,
            }],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "master-ball"},
            moves_by_id={33: "tackle"},
        )
        move_names = ["None", *(f"Move {move_id}" for move_id in range(1, 468))]
        move_names[33] = "Play Rough"
        enriched = enrich_trainer_dataset(
            {
                "game": "test",
                "source": {},
                "move_names": move_names,
                "records": [source],
            },
            pokedb,
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_trainer_pages(enriched, output)
            page = (output / "trainer-0000.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Youngster Tristan", page)
        self.assertIn('href="../../pokemon/bulbasaur/">Bulbasaur</a>', page)
        self.assertIn("Master Ball", page)
        self.assertIn("Play Rough", page)
        self.assertIn(
            "| [Route 202](../locations/header-343.md) | 343 | `R202` | "
            "(181, 818) | `329:0` |",
            page,
        )
        self.assertEqual(catalog["kind"], "trainers")
        self.assertEqual(catalog["records"][0]["min_level"], 5)
        self.assertEqual(
            catalog["records"][0]["party"],
            [{
                "name": "Bulbasaur",
                "level": 5,
                "pokemon_ref": {
                    "kind": "pokemon",
                    "id": 1,
                    "label": "Bulbasaur",
                    "url": "../pokemon/bulbasaur/",
                },
            }],
        )
        self.assertEqual(
            catalog["records"][0]["location_refs"][0]["url"],
            "../locations/header-343/",
        )


if __name__ == "__main__":
    unittest.main()
