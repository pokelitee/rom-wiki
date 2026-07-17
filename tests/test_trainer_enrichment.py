from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.pipeline.enrich import enrich_trainer_dataset
from romwiki.renderers.mkdocs import render_trainer_pages
from romwiki.sources import PokeDBGeneration


class TrainerEnrichmentTests(unittest.TestCase):
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
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "master-ball"},
            moves_by_id={33: "tackle"},
        )
        enriched = enrich_trainer_dataset(
            {"game": "test", "source": {}, "records": [source]}, pokedb
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_trainer_pages(enriched, output)
            page = (output / "trainer-0000.md").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("# Youngster Tristan", page)
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn("Master Ball", page)
        self.assertIn("Tackle", page)


if __name__ == "__main__":
    unittest.main()
