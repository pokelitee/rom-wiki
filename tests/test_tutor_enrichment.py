from __future__ import annotations

import unittest

from romwiki.pipeline.enrich import enrich_move_dataset, enrich_personal_dataset
from tests.test_enrichment import _source_record
from tests.test_evolution_enrichment import _reference_pokedb
from tests.test_move_enrichment import _source_record as _move_source_record


class TutorEnrichmentTests(unittest.TestCase):
    def test_joins_tutors_to_pokemon_and_moves(self) -> None:
        pokedb = _reference_pokedb()
        pokedb.moves_by_id.update(
            {move_id: f"move-{move_id}" for move_id in range(1, 468)}
        )
        tutors = _tutor_dataset()
        pokemon = enrich_personal_dataset(
            {
                "game": "test",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
            tutor_dataset=tutors,
        )
        moves = enrich_move_dataset(
            {
                "game": "test",
                "source": {"archive": "moves.narc"},
                "records": [_move_source_record(move_id) for move_id in range(471)],
            },
            pokedb,
            tutor_dataset=tutors,
        )

        self.assertEqual(pokemon["records"][1]["tutor_moves"][0]["move"]["slug"], "move-291")
        self.assertEqual(pokemon["records"][1]["tutor_moves"][0]["location"]["name"], "Route 212")
        self.assertEqual(moves["records"][291]["tutors"][0]["shard_costs"]["blue"], 4)
        self.assertEqual(
            moves["records"][291]["tutors"][0]["compatible_pokemon"][0]["slug"],
            "pokemon-1",
        )


def _tutor_dataset() -> dict:
    return {
        "game": "test",
        "source": {"overlay_id": 5},
        "location_names": ["Route 212"],
        "records": [
            {
                "tutor_id": 1,
                "move_id": 291,
                "shard_costs": {"red": 2, "blue": 4, "yellow": 2, "green": 0},
                "location_id": 0,
                "table_index": 0,
            }
        ],
        "compatibility": [
            {"personal_member": 1, "tutor_ids": [1], "table_index": 0}
        ],
    }


if __name__ == "__main__":
    unittest.main()
