from __future__ import annotations

import unittest
from typing import Any

from romwiki.pipeline.enrichment.moves import enrich_move_dataset
from romwiki.sources import PokeDBGeneration


class MoveEnrichmentTests(unittest.TestCase):
    def test_names_public_moves_and_preserves_internal_records(self) -> None:
        dataset: dict[str, Any] = {
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
