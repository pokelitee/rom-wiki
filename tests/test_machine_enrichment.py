from __future__ import annotations

import unittest

from romwiki.pipeline.enrich import enrich_move_dataset, enrich_personal_dataset
from tests.test_enrichment import _source_record
from tests.test_evolution_enrichment import _reference_pokedb
from tests.test_move_enrichment import _source_record as _move_source_record


class MachineEnrichmentTests(unittest.TestCase):
    def test_joins_machine_assignments_to_pokemon_and_moves(self) -> None:
        pokedb = _reference_pokedb()
        pokedb.moves_by_id.update(
            {move_id: f"move-{move_id}" for move_id in range(1, 468)}
        )
        machine_dataset = _machine_dataset()
        personal_records = [_source_record(member) for member in range(508)]
        personal_records[1]["machine_ids"] = [1, 100]

        pokemon = enrich_personal_dataset(
            {
                "game": "test",
                "source": {"archive": "personal.narc"},
                "records": personal_records,
            },
            pokedb,
            machine_dataset=machine_dataset,
        )
        moves = enrich_move_dataset(
            {
                "game": "test",
                "source": {"archive": "moves.narc"},
                "records": [_move_source_record(move_id) for move_id in range(471)],
            },
            pokedb,
            machine_dataset,
        )

        self.assertEqual(
            [machine["name"] for machine in pokemon["records"][1]["machines"]],
            ["TM01", "HM08"],
        )
        self.assertEqual(
            pokemon["records"][1]["machines"][0]["move"]["slug"], "move-1"
        )
        self.assertEqual(moves["records"][1]["machines"][0]["name"], "TM01")
        self.assertEqual(moves["records"][100]["machines"][0]["name"], "HM08")


def _machine_dataset() -> dict:
    records = []
    for machine_id in range(1, 101):
        kind = "tm" if machine_id <= 92 else "hm"
        number = machine_id if kind == "tm" else machine_id - 92
        records.append(
            {
                "machine_id": machine_id,
                "kind": kind,
                "number": number,
                "move_id": machine_id,
                "table_index": machine_id - 1,
                "name": f"{kind.upper()}{number:02}",
            }
        )
    return {
        "game": "test",
        "source": {"offset": 100},
        "records": records,
    }


if __name__ == "__main__":
    unittest.main()
