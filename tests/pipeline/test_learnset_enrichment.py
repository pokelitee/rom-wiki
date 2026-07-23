from __future__ import annotations

import unittest

from romwiki.pipeline.enrich import enrich_personal_dataset
from romwiki.sources import PokeDBGeneration
from tests.pipeline.test_enrichment import FORM_SPECIES, _source_record


class LearnsetEnrichmentTests(unittest.TestCase):
    def test_associates_named_moves_with_species_members(self) -> None:
        defaults = {
            pokemon_id: {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species": f"pokemon-{pokemon_id}",
            }
            for pokemon_id in range(1, 494)
        }
        for pokemon_id, species in (
            (386, "deoxys"),
            (413, "wormadam"),
            (479, "rotom"),
            (487, "giratina"),
            (492, "shaymin"),
        ):
            defaults[pokemon_id] = {
                "id": pokemon_id,
                "name": f"{species}-default",
                "species": species,
            }
        variants = {
            name: {"id": 10000 + index, "name": name, "species": species}
            for index, (name, species) in enumerate(FORM_SPECIES.items())
        }
        by_name = {item["name"]: item for item in defaults.values()}
        by_name.update(variants)
        pokedb = PokeDBGeneration(
            pokemon_by_id=defaults,
            pokemon_by_name=by_name,
            pokemon_by_species={item["species"]: item for item in defaults.values()},
            abilities_by_id={},
            items_by_id={},
            moves_by_id={33: "tackle", 45: "growl"},
        )
        learnsets = [_learnset(member) for member in range(508)]
        learnsets[1]["moves"] = [
            {"level": 1, "move_id": 33},
            {"level": 1, "move_id": 45},
        ]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "wotbl.narc"},
                "records": learnsets,
            },
        )

        self.assertEqual(
            enriched["records"][1]["level_up_moves"],
            [
                {
                    "level": 1,
                    "move": {"id": 33, "slug": "tackle", "name": "Tackle"},
                },
                {
                    "level": 1,
                    "move": {"id": 45, "slug": "growl", "name": "Growl"},
                },
            ],
        )
        self.assertEqual(
            enriched["records"][1]["learnset_provenance"]["archive"],
            "wotbl.narc",
        )


def _learnset(member: int) -> dict:
    return {
        "species_id": member,
        "moves": [],
        "provenance": {
            "source": "rom",
            "archive": "wotbl.narc",
            "member": member,
        },
    }


if __name__ == "__main__":
    unittest.main()
