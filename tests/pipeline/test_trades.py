from __future__ import annotations

import unittest

from romwiki.pipeline.trades import enrich_npc_trade_dataset
from romwiki.util.errors import DataSourceError


class TradeEnrichmentTests(unittest.TestCase):
    def test_resolves_offered_forms_and_requested_species(self) -> None:
        trades = {
            "game": "white-us",
            "engine": "gen5_bw",
            "dataset": "trades",
            "records": [
                {
                    "trade_id": 1,
                    "offered_species_id": 550,
                    "offered_forme_id": 1,
                    "requested_species_id": 1,
                    "held_item_id": None,
                }
            ],
        }
        pokemon = {
            "game": "white-us",
            "records": [
                _pokemon(1, 1, "bulbasaur", None),
                _pokemon(550, 550, "basculin-red-striped", None),
                _pokemon(651, 550, "basculin-blue-striped", "blue-striped"),
            ],
        }

        record = enrich_npc_trade_dataset(trades, pokemon)["records"][0]

        self.assertEqual(
            record["offered_pokemon"]["slug"], "basculin-blue-striped"
        )
        self.assertEqual(record["requested_pokemon"]["slug"], "bulbasaur")

    def test_rejects_a_mismatched_pokemon_dataset(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "same game"):
            enrich_npc_trade_dataset(
                {"game": "black", "engine": "gen5_bw", "records": []},
                {"game": "white", "records": []},
            )


def _pokemon(
    member: int,
    dex: int,
    slug: str,
    form: str | None,
) -> dict:
    return {
        "member": member,
        "national_dex_id": dex,
        "name": slug,
        "slug": slug,
        "form": form,
        "public": True,
    }


if __name__ == "__main__":
    unittest.main()
