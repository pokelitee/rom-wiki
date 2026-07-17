from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.pipeline.enrich import enrich_personal_dataset
from romwiki.renderers.mkdocs import render_pokemon_pages
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
        defaults = {
            pokemon_id: {
                "id": pokemon_id,
                "name": f"pokemon-{pokemon_id}",
                "species": f"pokemon-{pokemon_id}",
            }
            for pokemon_id in range(1, 494)
        }
        for pokemon_id, species in (
            (386, "deoxys"), (413, "wormadam"), (479, "rotom"),
            (487, "giratina"), (492, "shaymin"),
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
        )
        records = [_source_record(member) for member in range(508)]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "source": {"archive": "personal.narc"},
                "records": records,
            },
            pokedb,
        )

        self.assertEqual(enriched["public_record_count"], 505)
        self.assertFalse(enriched["records"][494]["public"])
        self.assertEqual(enriched["records"][496]["slug"], "deoxys-attack")
        self.assertEqual(enriched["records"][496]["national_dex_id"], 386)

    def test_renders_a_page_and_index(self) -> None:
        record = {
            "public": True,
            "slug": "bulbasaur",
            "name": "Bulbasaur",
            "national_dex_id": 1,
            "base_stats": {
                "hp": 45, "attack": 49, "defense": 49, "speed": 45,
                "special_attack": 65, "special_defense": 65,
            },
            "types": [{"name": "grass"}, {"name": "poison"}],
            "abilities": [{"name": "overgrow"}],
            "catch_rate": 45,
            "base_experience": 64,
            "base_friendship": 70,
            "hatch_cycles": 20,
            "growth_rate": {"name": "medium-slow"},
            "egg_groups": [{"name": "monster"}, {"name": "grass"}],
            "machines": [
                {
                    "name": "TM01",
                    "move": {"id": 264, "slug": "focus-punch", "name": "Focus Punch"},
                }
            ],
            "tutor_moves": [
                {
                    "move": {"id": 402, "slug": "seed-bomb", "name": "Seed Bomb"},
                    "location": {"id": 1, "name": "Survival Area"},
                    "shard_costs": {"red": 4, "blue": 0, "yellow": 0, "green": 4},
                }
            ],
            "level_up_moves": [
                {
                    "level": 1,
                    "move": {"id": 33, "slug": "tackle", "name": "Tackle"},
                }
            ],
            "learnset_provenance": {"archive": "wotbl.narc", "member": 1},
            "evolutions": [
                {
                    "method_id": 4,
                    "method": {"id": 4, "name": "level"},
                    "parameter_data": {"kind": "level", "value": 16},
                    "target": {"id": 2, "slug": "ivysaur", "name": "Ivysaur"},
                },
                {
                    "method_id": 7,
                    "method": {"id": 7, "name": "use-item"},
                    "parameter_data": {
                        "kind": "item",
                        "id": 221,
                        "name": "King's Rock",
                    },
                    "target": {"id": 2, "slug": "ivysaur", "name": "Ivysaur"},
                },
            ],
            "evolution_provenance": {"archive": "evo.narc", "member": 1},
            "provenance": {"archive": "personal.narc", "member": 1},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_pokemon_pages({"records": [record]}, output)
            page = (output / "bulbasaur.md").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("# Bulbasaur", page)
        self.assertIn("| 45 | 49 |", page)
        self.assertIn("[Tackle](../moves/tackle.md)", page)
        self.assertIn("[Ivysaur](ivysaur.md)", page)
        self.assertIn("Level 16", page)
        self.assertIn("Use King's Rock", page)
        self.assertIn("[Focus Punch](../moves/focus-punch.md)", page)
        self.assertIn("[Seed Bomb](../moves/seed-bomb.md)", page)
        self.assertIn("4 Red, 4 Green", page)


def _source_record(member: int) -> dict:
    return {
        "species_id": member,
        "base_stats": {
            "hp": 1, "attack": 1, "defense": 1, "speed": 1,
            "special_attack": 1, "special_defense": 1,
        },
        "type_ids": [0, 0],
        "catch_rate": 1,
        "base_experience": 1,
        "ev_yields": {
            "hp": 0, "attack": 0, "defense": 0, "speed": 0,
            "special_attack": 0, "special_defense": 0,
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
