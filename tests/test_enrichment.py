from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from romwiki.pipeline.enrich import enrich_personal_dataset
from romwiki.renderers.mkdocs import render_pokemon_pages
from romwiki.renderers.mkdocs.pokemon import (
    _evolution_chain,
    _index_preevolutions,
    _sprite_gallery,
)
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
            abilities_by_id={65: "overgrow"},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(508)]
        records[1]["type_ids"] = [9, 9]
        records[1]["ability_ids"] = [65, 65]
        ability_names = [f"Ability {ability_id}" for ability_id in range(124)]
        ability_names[65] = "Overgrow"

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "source": {"archive": "personal.narc"},
                "ability_names": ability_names,
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
            {"id": 65, "slug": "overgrow", "name": "Overgrow"},
        )

    def test_renders_a_page_and_index(self) -> None:
        record = {
            "public": True,
            "slug": "bulbasaur",
            "name": "Bulbasaur",
            "national_dex_id": 1,
            "form": None,
            "reference": {
                "version": "platinum",
                "source": "PokéDB / PokéAPI",
                "source_url": "https://pokeapi.co/api/v2/pokemon/1/",
                "genus": "Seed Pokémon",
                "height_dm": 7,
                "weight_hg": 69,
                "flavor_text": "A seed was planted on its back at birth.",
                "flavor_text_version": "platinum",
                "base_stats": {
                    "hp": 45, "attack": 49, "defense": 49, "speed": 45,
                    "special_attack": 60, "special_defense": 65,
                },
                "types": ["grass", "poison"],
                "abilities": ["overgrow"],
            },
            "base_stats": {
                "hp": 45, "attack": 49, "defense": 49, "speed": 45,
                "special_attack": 65, "special_defense": 65,
            },
            "types": [{"name": "grass"}, {"name": "grass"}],
            "abilities": [{"name": "overgrow"}],
            "catch_rate": 45,
            "base_experience": 64,
            "base_friendship": 70,
            "ev_yields": {
                "hp": 0, "attack": 0, "defense": 0, "speed": 0,
                "special_attack": 1, "special_defense": 0,
            },
            "gender_ratio": 31,
            "safari_flee_rate": 0,
            "hatch_cycles": 20,
            "growth_rate": {"name": "medium-slow"},
            "egg_groups": [{"name": "monster"}, {"name": "grass"}],
            "held_items": [
                {"rarity": "common", "id": 0, "name": None},
                {"rarity": "rare", "id": 81, "name": "Moon Stone"},
            ],
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
                },
                {
                    "kind": "special",
                    "move": {
                        "id": 338,
                        "slug": "frenzy-plant",
                        "name": "Frenzy Plant",
                    },
                    "location": {"name": "Route 228"},
                    "minimum_friendship": 255,
                },
            ],
            "level_up_moves": [
                {
                    "level": 1,
                    "move": {"id": 33, "slug": "tackle", "name": "Tackle"},
                }
            ],
            "egg_moves": [
                {"id": 130, "slug": "skull-bash", "name": "Skull Bash"}
            ],
            "egg_move_provenance": {"overlay_offset": 0x29222, "table_index": 0},
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
                        "slug": "kings-rock",
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
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Bulbasaur", page)
        self.assertEqual(page.count("rw-type--grass"), 1)
        self.assertIn('<span class="rw-stat__value">45</span>', page)
        self.assertNotIn("+5", page)
        self.assertIn("A seed was planted on its back at birth.", page)
        self.assertIn("0.7 m (2′4″)", page)
        self.assertIn("1 Sp. Atk", page)
        self.assertIn("87.5% male / 12.5% female", page)
        self.assertNotIn("Base typing", page)
        self.assertIn("[Tackle](../moves/tackle.md)", page)
        self.assertIn("[Skull Bash](../moves/skull-bash.md)", page)
        self.assertIn("| Move | Type | Class | Power | Accuracy | PP |", page)
        self.assertIn("## Learnset", page)
        self.assertIn("`0x29222`", page)
        self.assertIn(
            '<a class="rw-evolution-node" href="../ivysaur/">', page
        )
        self.assertIn(
            '<span class="rw-evolution-node__name">Ivysaur</span>', page
        )
        self.assertIn("Level 16", page)
        self.assertIn(
            'Use <a href="../../items/kings-rock/">King&#x27;s Rock</a>', page
        )
        self.assertIn("[Focus Punch](../moves/focus-punch.md)", page)
        self.assertIn("## Wild held items", page)
        self.assertIn("| Rare | Moon Stone | 81 |", page)
        self.assertIn("[Seed Bomb](../moves/seed-bomb.md)", page)
        self.assertIn("4 Red, 4 Green", page)
        self.assertIn("[Frenzy Plant](../moves/frenzy-plant.md)", page)
        self.assertIn("Friendship 255", page)
        self.assertEqual(catalog["schema_version"], 1)
        self.assertEqual(catalog["kind"], "pokemon")
        self.assertEqual(catalog["records"][0]["bst"], 318)
        self.assertEqual(catalog["records"][0]["egg_groups"], ["monster", "grass"])
        self.assertEqual(catalog["records"][0]["url"], "bulbasaur/")

    def test_indexes_reverse_evolution_links_for_public_records(self) -> None:
        records = [
            {
                "public": True,
                "member": 1,
                "national_dex_id": 1,
                "slug": "bulbasaur",
                "name": "Bulbasaur",
                "evolutions": [
                    {
                        "method_id": 4,
                        "target": {
                            "id": 2,
                            "slug": "ivysaur",
                            "name": "Ivysaur",
                        },
                    }
                ],
            },
            {
                "public": True,
                "member": 2,
                "national_dex_id": 2,
                "slug": "ivysaur",
                "name": "Ivysaur",
                "evolutions": [],
            },
        ]

        index = _index_preevolutions(records)

        self.assertEqual(index["ivysaur"][0]["source"]["slug"], "bulbasaur")
        self.assertEqual(index["ivysaur"][0]["evolution"]["method_id"], 4)

    def test_renders_complete_branching_evolution_chain(self) -> None:
        eevee = _evolution_record("eevee", "Eevee", 133)
        vaporeon = _evolution_record("vaporeon", "Vaporeon", 134)
        jolteon = _evolution_record("jolteon", "Jolteon", 135)
        eevee["evolutions"] = [
            _evolution("vaporeon", "Vaporeon", 134, "Water Stone"),
            _evolution("jolteon", "Jolteon", 135, "Thunder Stone"),
        ]

        chain = "\n".join(
            _evolution_chain(
                [eevee, vaporeon, jolteon], jolteon, "pokemon/jolteon.md"
            )
        )

        self.assertIn("Eevee", chain)
        self.assertIn("Vaporeon", chain)
        self.assertIn("Jolteon", chain)
        self.assertIn("Water Stone", chain)
        self.assertIn("rw-evolution-node--current", chain)
        self.assertIn('aria-current="page"', chain)
        self.assertIn('class="rw-evolution-node__current">Current', chain)
        self.assertIn('class="rw-evolution-node__dex">#135', chain)
        self.assertIn('class="rw-evolution-step"', chain)
        self.assertIn('class="rw-evolution-branches"', chain)
        self.assertIn('href="../vaporeon/"', chain)


class SpriteGalleryTests(unittest.TestCase):
    def test_omits_the_section_when_no_sprites_are_available(self) -> None:
        self.assertEqual(_sprite_gallery({"name": "Missingno", "sprites": []}), [])
        self.assertEqual(_sprite_gallery({"name": "Missingno"}), [])

    def test_still_renders_a_single_known_sprite(self) -> None:
        lines = _sprite_gallery(
            {
                "name": "Bulbasaur",
                "sprites": [
                    {
                        "key": "front_default",
                        "label": "Front",
                        "url": "https://example.test/front.png",
                    }
                ],
            }
        )

        page = "\n".join(lines)
        self.assertIn("## Sprites", page)
        self.assertIn('src="https://example.test/front.png"', page)
        self.assertIn('<span class="rw-sprite-matrix__label">Front</span>', page)

    def test_groups_variants_into_a_normal_and_shiny_matrix(self) -> None:
        lines = _sprite_gallery(
            {
                "name": "Bulbasaur",
                "sprites": [
                    {"key": "front_default", "label": "Front", "url": "https://example.test/front.png"},
                    {"key": "front_shiny", "label": "Front, shiny", "url": "https://example.test/front-shiny.png"},
                    {"key": "back_default", "label": "Back", "url": "https://example.test/back.png"},
                ],
            }
        )

        page = "\n".join(lines)
        self.assertIn('<span class="rw-sprite-matrix__label">Front</span>', page)
        self.assertIn('<span class="rw-sprite-matrix__label">Back</span>', page)
        self.assertNotIn("Front, female", page)
        self.assertIn('src="https://example.test/front.png"', page)
        self.assertIn('src="https://example.test/front-shiny.png"', page)
        self.assertIn('src="https://example.test/back.png"', page)
        self.assertIn('rw-sprite-matrix__cell--empty">—<', page)


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


def _evolution_record(slug: str, name: str, member: int) -> dict:
    return {
        "slug": slug,
        "name": name,
        "member": member,
        "national_dex_id": member,
        "sprite": None,
        "evolutions": [],
    }


def _evolution(slug: str, name: str, member: int, item: str) -> dict:
    return {
        "method_id": 7,
        "method": {"id": 7, "name": "use-item"},
        "parameter_data": {"kind": "item", "id": 1, "name": item},
        "target": {"id": member, "slug": slug, "name": name},
    }


if __name__ == "__main__":
    unittest.main()
