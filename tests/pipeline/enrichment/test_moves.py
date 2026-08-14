from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.enrichment.moves import enrich_move_dataset
from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_move_pages
from romwiki.sources import PokeDBGeneration


class MoveEnrichmentTests(unittest.TestCase):
    def test_names_public_moves_and_preserves_internal_records(self) -> None:
        dataset = {
            "game": "test",
            "engine": "gen4_hgss",
            "source": {"archive": "moves.narc"},
            "records": [_source_record(move_id) for move_id in range(471)],
        }
        dataset["records"][85]["type_id"] = 9
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
            moves_by_id={move_id: f"move-{move_id}" for move_id in range(1, 468)},
        )

        default_enriched = enrich_move_dataset(dataset, pokedb)
        dataset["type_names"] = [
            "Normal",
            "Fighting",
            "Flying",
            "Poison",
            "Ground",
            "Rock",
            "Bug",
            "Ghost",
            "Steel",
            "Fairy",
            "Fire",
            "Water",
            "Grass",
            "Electric",
            "Psychic",
            "Ice",
            "Dragon",
            "Dark",
        ]
        dataset["move_names"] = [
            "None",
            *(f"Move {move_id}" for move_id in range(1, 468)),
        ]
        dataset["move_names"][85] = "Moonblast"
        enriched = enrich_move_dataset(
            dataset,
            pokedb,
            type_names={9: "fallback-type"},
            move_names={85: "fallback-move"},
        )

        self.assertEqual(enriched["public_record_count"], 467)
        self.assertEqual(default_enriched["records"][85]["type"]["name"], "unknown")
        self.assertEqual(enriched["records"][85]["slug"], "moonblast")
        self.assertEqual(enriched["records"][85]["name"], "Moonblast")
        self.assertEqual(enriched["records"][85]["type"]["name"], "fairy")
        self.assertEqual(
            enriched["records"][85]["replaces"],
            {"slug": "move-85", "name": "Move 85"},
        )
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
                    "compatible_pokemon": [{"slug": "dragonite", "name": "Dragonite"}],
                }
            ],
            "egg_move_pokemon": [{"slug": "pichu", "name": "Pichu"}],
        }
        relationships = build_relationship_index(
            {
                "pokemon": {
                    "game": "test",
                    "records": [
                        {
                            "member": 25,
                            "name": "Pikachu",
                            "slug": "pikachu",
                            "form": None,
                            "public": True,
                            "level_up_moves": [{"level": 26, "move": {"id": 85}}],
                            "machines": [
                                {
                                    "id": 24,
                                    "kind": "tm",
                                    "name": "TM24",
                                    "move": {"id": 85},
                                }
                            ],
                        }
                    ],
                }
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "old-move-name.md"
            stale_page.write_text("stale", encoding="utf-8")
            count = render_move_pages(
                {"records": [record]}, output, relationships=relationships
            )
            page = (output / "thunderbolt.md").read_text(encoding="utf-8")
            index = (output / "index.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertFalse(stale_page.exists())
        self.assertIn("# Thunderbolt", page)
        self.assertIn("<dt>Power</dt><dd>90</dd>", page)
        self.assertIn("## Additional battle properties", page)
        self.assertNotIn("## Battle properties", page)
        self.assertIn("`0x0010`", page)
        self.assertIn("<dt>Machine</dt><dd>TM24</dd>", page)
        self.assertIn("Route 210 — Friendship 255", page)
        self.assertIn("[Dragonite](../pokemon/dragonite.md)", page)
        self.assertIn("## Learned by", page)
        self.assertIn("### Level up", page)
        self.assertIn("[Pikachu](../pokemon/pikachu.md)", page)
        self.assertIn("| 26 |", page)
        self.assertIn("### Machines", page)
        self.assertIn("| TM24 |", page)
        self.assertIn("### Move tutors", page)
        self.assertIn("### Egg moves", page)
        self.assertIn("[Pichu](../pokemon/pichu.md)", page)
        self.assertIn("[Thunderbolt](thunderbolt.md)", index)
        self.assertEqual(catalog["kind"], "moves")
        self.assertEqual(
            catalog["records"][0]["access_methods"],
            ["level up", "machine", "move tutor", "egg move"],
        )
        self.assertEqual(catalog["records"][0]["url"], "thunderbolt/")
        self.assertEqual(
            catalog["records"][0]["learner_counts"],
            {"level_up": 1, "machine": 1, "move_tutor": 1, "egg_move": 1},
        )
        self.assertEqual(catalog["records"][0]["learner_count"], 3)

    def test_renders_empty_move_compatibility_sections(self) -> None:
        record = {
            **_source_record(1),
            "slug": "pound",
            "name": "Pound",
            "public": True,
            "type": {"id": 0, "name": "normal"},
            "damage_class": {"id": 0, "name": "physical"},
            "machines": [],
            "tutors": [],
            "egg_move_pokemon": [],
            "effect_chance": 0,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_move_pages(
                {"records": [record]},
                output,
                relationships=build_relationship_index({}),
            )
            page = (output / "pound.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("## Learned by", page)
        self.assertIn("### Move tutors", page)
        self.assertIn("No compatible move tutors.", page)
        self.assertIn("### Egg moves", page)
        self.assertIn("No egg move learners.", page)
        self.assertNotIn("## Additional battle properties", page)
        self.assertEqual(catalog["records"][0]["access_methods"], ["no known learners"])


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
