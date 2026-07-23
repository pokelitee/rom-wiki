from __future__ import annotations

import unittest

from romwiki.pipeline.enrich import enrich_personal_dataset
from romwiki.sources import PokeDBGeneration
from tests.test_enrichment import FORM_SPECIES, _source_record


class EvolutionEnrichmentTests(unittest.TestCase):
    def test_resolves_methods_parameters_and_target_species(self) -> None:
        pokedb = _reference_pokedb()
        records = [_evolution_set(member) for member in range(508)]
        records[25]["evolutions"] = [
            {"method_id": 7, "parameter": 83, "target_species_id": 26}
        ]
        item_names = [f"Item {item_id}" for item_id in range(468)]
        item_names[83] = "Thunder Stone"

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
            evolution_dataset={
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "evo.narc"},
                "item_names": item_names,
                "records": records,
            },
        )

        evolution = enriched["records"][25]["evolutions"][0]
        self.assertEqual(evolution["method"]["name"], "use-item")
        self.assertEqual(evolution["parameter_data"]["name"], "Thunder Stone")
        self.assertEqual(evolution["target"]["slug"], "pokemon-26")
        self.assertEqual(
            enriched["records"][25]["evolution_provenance"]["archive"],
            "evo.narc",
        )

    def test_party_species_parameter_uses_pokemon_reference_kind(self) -> None:
        pokedb = _reference_pokedb()
        records = [_evolution_set(member) for member in range(508)]
        records[223]["evolutions"] = [
            {"method_id": 21, "parameter": 224, "target_species_id": 226}
        ]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "personal.narc"},
                "records": [_source_record(member) for member in range(508)],
            },
            pokedb,
            evolution_dataset={
                "game": "test",
                "engine": "gen4_dppt",
                "source": {"archive": "evo.narc"},
                "item_names": [],
                "records": records,
            },
        )

        parameter = enriched["records"][223]["evolutions"][0]["parameter_data"]
        self.assertEqual(parameter["kind"], "pokemon")
        self.assertEqual(parameter["slug"], "pokemon-224")


def _reference_pokedb() -> PokeDBGeneration:
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
    return PokeDBGeneration(
        pokemon_by_id=defaults,
        pokemon_by_name=by_name,
        pokemon_by_species={item["species"]: item for item in defaults.values()},
        abilities_by_id={},
        items_by_id={83: "thunder-stone"},
    )


def _evolution_set(member: int) -> dict:
    return {
        "species_id": member,
        "evolutions": [],
        "provenance": {"source": "rom", "archive": "evo.narc", "member": member},
    }


if __name__ == "__main__":
    unittest.main()
