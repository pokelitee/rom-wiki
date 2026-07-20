from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from romwiki.pipeline.enrich import enrich_move_dataset
from romwiki.renderers.mkdocs import render_move_pages
from romwiki.sources import PokeDBGeneration


class MoveEnrichmentTests(unittest.TestCase):
    def test_names_public_moves_and_preserves_internal_records(self) -> None:
        dataset = {
            "game": "test",
            "source": {"archive": "moves.narc"},
            "records": [_source_record(move_id) for move_id in range(471)],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
            moves_by_id={move_id: f"move-{move_id}" for move_id in range(1, 468)},
        )

        enriched = enrich_move_dataset(dataset, pokedb)

        self.assertEqual(enriched["public_record_count"], 467)
        self.assertEqual(enriched["records"][85]["slug"], "move-85")
        self.assertEqual(enriched["records"][85]["type"]["name"], "electric")
        self.assertEqual(enriched["records"][85]["damage_class"]["name"], "special")
        self.assertFalse(enriched["records"][468]["public"])

    def test_renders_move_page_and_index(self) -> None:
        record = {
            **_source_record(85),
            "slug": "thunderbolt",
            "name": "Thunderbolt",
            "public": True,
            "type": {"id": 13, "name": "electric"},
            "damage_class": {"id": 1, "name": "special"},
            "machines": [{"name": "TM24"}],
            "tutors": [
                {
                    "kind": "special",
                    "location": {"name": "Route 210"},
                    "minimum_friendship": 255,
                    "compatible_pokemon": [
                        {"slug": "dragonite", "name": "Dragonite"}
                    ],
                }
            ],
            "egg_move_pokemon": [
                {"slug": "pichu", "name": "Pichu"}
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_move_pages({"records": [record]}, output)
            page = (output / "thunderbolt.md").read_text(encoding="utf-8")
            index = (output / "index.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Thunderbolt", page)
        self.assertIn("| Power | 90 |", page)
        self.assertIn("`0x0010`", page)
        self.assertIn("| Machine | TM24 |", page)
        self.assertIn("Route 210 — Friendship 255", page)
        self.assertIn("[Dragonite](../pokemon/dragonite.md)", page)
        self.assertIn("## Egg move learners", page)
        self.assertIn("[Pichu](../pokemon/pichu.md)", page)
        self.assertIn("[Thunderbolt](thunderbolt.md)", index)
        self.assertEqual(catalog["kind"], "moves")
        self.assertEqual(
            catalog["records"][0]["access_methods"],
            ["machine", "move tutor", "egg move"],
        )
        self.assertEqual(catalog["records"][0]["url"], "thunderbolt/")


def _source_record(move_id: int) -> dict:
    return {
        "move_id": move_id,
        "effect_id": 6,
        "damage_class_id": 1,
        "power": 90,
        "type_id": 13,
        "accuracy": 100,
        "pp": 15,
        "effect_chance": 10,
        "target_id": 0x10,
        "priority": 0,
        "flags": 0x12,
        "contest_effect_id": 17,
        "contest_type_id": 3,
        "provenance": {"source": "rom", "archive": "moves.narc", "member": move_id},
    }


if __name__ == "__main__":
    unittest.main()
