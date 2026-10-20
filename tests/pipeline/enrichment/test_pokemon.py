from __future__ import annotations

import unittest
from typing import Any

from romwiki.pipeline.enrichment.pokemon import enrich_personal_dataset
from romwiki.sources import PokeDBGeneration

FORM_SPECIES = {
    "deoxys-attack": "deoxys",
    "deoxys-defense": "deoxys",
    "deoxys-speed": "deoxys",
    "wormadam-sandy": "wormadam",
    "wormadam-trash": "wormadam",
    "giratina-origin": "giratina",
    "shaymin-sky": "shaymin",
    "rotom-heat": "rotom",
    "rotom-wash": "rotom",
    "rotom-frost": "rotom",
    "rotom-fan": "rotom",
    "rotom-mow": "rotom",
}


class PersonalEnrichmentTests(unittest.TestCase):
    def test_maps_public_species_forms_and_internal_records(self) -> None:
        defaults: dict[int, dict[str, Any]] = {
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
            abilities_by_id={65: "overgrow"},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(508)]
        records[1]["type_ids"] = [9, 9]
        records[1]["ability_ids"] = [65, 65]
        ability_names = [f"Ability {ability_id}" for ability_id in range(124)]
        ability_names[65] = "Overgrow"
        pokemon_names = ["-----"] + [f"Rom-{index}" for index in range(1, 496)]
        pokemon_names[1] = "MR. MIME"
        pokemon_names[494] = "Egg"
        pokemon_names[495] = "Bad Egg"

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_platinum",
                "source": {"archive": "personal.narc"},
                "ability_names": ability_names,
                "pokemon_names": pokemon_names,
                "records": records,
            },
            pokedb,
            type_names={9: "fairy"},
        )
        hgss_enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen4_hgss",
                "source": {"archive": "a/0/0/2"},
                "ability_names": ability_names,
                "pokemon_names": pokemon_names,
                "records": records,
            },
            pokedb,
            type_names={9: "fairy"},
        )

        self.assertEqual(enriched["public_record_count"], 505)
        self.assertFalse(enriched["records"][494]["public"])
        self.assertEqual(enriched["records"][496]["slug"], "deoxys-attack")
        self.assertEqual(enriched["records"][496]["national_dex_id"], 386)
        self.assertEqual(enriched["records"][1]["types"][0], {"id": 9, "name": "fairy"})
        self.assertEqual(
            enriched["records"][1]["abilities"][0],
            {"id": 65, "slug": "overgrow", "name": "Overgrow", "is_hidden": False},
        )
        # ROM names win for regular species (recapitalized from vanilla caps);
        # form members keep their slug-derived form labels.
        self.assertEqual(enriched["records"][1]["name"], "Mr. Mime")
        self.assertEqual(enriched["records"][2]["name"], "Rom-2")
        self.assertEqual(enriched["records"][496]["name"], "Deoxys Attack")
        self.assertEqual(hgss_enriched["public_record_count"], 505)
        self.assertEqual(hgss_enriched["records"][496]["slug"], "deoxys-attack")

    def test_resolves_gen5_alternate_formes_and_battle_only_transformations(
        self,
    ) -> None:
        defaults: dict[int, dict[str, Any]] = {
            pokemon_id: {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species": f"pokemon-{pokemon_id}",
            }
            for pokemon_id in range(1, 650)
        }
        for pokemon_id, name, species in (
            (386, "deoxys", "deoxys"),
            (413, "wormadam", "wormadam"),
            (487, "giratina", "giratina"),
            (492, "shaymin", "shaymin"),
            (479, "rotom", "rotom"),
            (550, "basculin", "basculin"),
            (351, "castform", "castform"),
            (555, "darmanitan-standard", "darmanitan"),
            (648, "meloetta-aria", "meloetta"),
        ):
            defaults[pokemon_id] = {"id": pokemon_id, "name": name, "species": species}
        gen5_form_species = {
            "deoxys-attack": "deoxys",
            "deoxys-defense": "deoxys",
            "deoxys-speed": "deoxys",
            "wormadam-sandy": "wormadam",
            "wormadam-trash": "wormadam",
            "shaymin-sky": "shaymin",
            "giratina-origin": "giratina",
            "rotom-heat": "rotom",
            "rotom-wash": "rotom",
            "rotom-frost": "rotom",
            "rotom-fan": "rotom",
            "rotom-mow": "rotom",
            "basculin-blue-striped": "basculin",
        }
        variants = {
            name: {"id": 10000 + index, "name": name, "species": species}
            for index, (name, species) in enumerate(gen5_form_species.items())
        }
        by_name = {item["name"]: item for item in defaults.values()}
        by_name.update(variants)
        pokedb = PokeDBGeneration(
            pokemon_by_id=defaults,
            pokemon_by_name=by_name,
            pokemon_by_species={item["species"]: item for item in defaults.values()},
            abilities_by_id={},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(668)]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": "gen5_bw",
                "source": {"archive": "personal.narc"},
                "records": records,
            },
            pokedb,
            type_names={0: "normal"},
        )

        deoxys_attack = enriched["records"][650]
        self.assertTrue(deoxys_attack["public"])
        self.assertEqual(deoxys_attack["slug"], "deoxys-attack")
        self.assertEqual(deoxys_attack["national_dex_id"], 386)

        castform_sunny = enriched["records"][662]
        self.assertFalse(castform_sunny["public"])
        self.assertNotIn("battle_forms", castform_sunny)

        castform = enriched["records"][351]
        self.assertEqual(
            [form["label"] for form in castform["battle_forms"]],
            ["Sunny Form", "Rainy Form", "Snowy Form"],
        )
        self.assertEqual(
            castform["battle_forms"][0]["base_stats"], castform_sunny["base_stats"]
        )

        darmanitan = enriched["records"][555]
        self.assertEqual(
            [form["label"] for form in darmanitan["battle_forms"]], ["Zen Mode"]
        )

        meloetta = enriched["records"][648]
        self.assertEqual(
            [form["label"] for form in meloetta["battle_forms"]], ["Pirouette Forme"]
        )


def _source_record(member: int) -> dict:
    return {
        "species_id": member,
        "base_stats": {
            "hp": 1,
            "attack": 1,
            "defense": 1,
            "speed": 1,
            "special_attack": 1,
            "special_defense": 1,
        },
        "type_ids": [0, 0],
        "catch_rate": 1,
        "base_experience": 1,
        "ev_yields": {
            "hp": 0,
            "attack": 0,
            "defense": 0,
            "speed": 0,
            "special_attack": 0,
            "special_defense": 0,
        },
        "wild_held_items": {"common": 0, "rare": 0},
        "gender_ratio": 255,
        "hatch_cycles": 1,
        "base_friendship": 1,
        "growth_rate_id": 0,
        "egg_group_ids": [0, 0],
        "ability_ids": [0, 0],
        "safari_flee_rate": 0,
        "body_color_id": 10 if member in {494, 495} else 0,
        "flip_sprite": False,
        "machine_ids": [],
        "provenance": {"source": "rom", "archive": "personal.narc", "member": member},
    }


if __name__ == "__main__":
    unittest.main()
