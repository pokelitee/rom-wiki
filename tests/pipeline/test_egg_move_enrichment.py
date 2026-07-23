from __future__ import annotations

import unittest

from romwiki.pipeline.enrich import enrich_move_dataset, enrich_personal_dataset
from tests.pipeline.test_enrichment import _source_record
from tests.pipeline.test_evolution_enrichment import _reference_pokedb
from tests.pipeline.test_move_enrichment import _source_record as _move_source_record


class EggMoveEnrichmentTests(unittest.TestCase):
    def test_joins_egg_moves_to_pokemon_and_moves(self) -> None:
        pokedb = _reference_pokedb()
        pokedb.moves_by_id.update(
            {move_id: f"move-{move_id}" for move_id in range(1, 468)}
        )
        pokedb.moves_by_id.update({113: "light-screen", 130: "skull-bash"})
        egg_moves = {
            "game": "test",
            "engine": "gen4_dppt",
            "source": {"overlay_id": 5, "table_offset": 0x100},
            "records": [
                {
                    "species_id": 1,
                    "move_ids": [113, 130],
                    "table_index": 0,
                    "overlay_offset": 0x100,
                }
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
            egg_move_dataset=egg_moves,
        )
        moves = enrich_move_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "moves.narc"},
                "records": [_move_source_record(move_id) for move_id in range(471)],
            },
            pokedb,
            egg_move_dataset=egg_moves,
        )

        self.assertEqual(
            [move["slug"] for move in pokemon["records"][1]["egg_moves"]],
            ["light-screen", "skull-bash"],
        )
        self.assertEqual(
            pokemon["records"][1]["egg_move_provenance"]["overlay_offset"],
            0x100,
        )
        self.assertEqual(
            moves["records"][113]["egg_move_pokemon"][0]["slug"],
            "pokemon-1",
        )


if __name__ == "__main__":
    unittest.main()
