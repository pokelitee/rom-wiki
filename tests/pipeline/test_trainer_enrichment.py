from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.enrich import _enrich_trainer, enrich_trainer_dataset
from romwiki.renderers.mkdocs import render_trainer_pages
from romwiki.sources import PokeDBGeneration


class TrainerEnrichmentTests(unittest.TestCase):
    def test_labels_burmy_cosmetic_cloaks(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={
                412: {"id": 412, "name": "burmy", "species": "burmy"}
            },
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 0,
            "class_id": 0,
            "class_gender": "male",
            "has_custom_moves": False,
            "reward_item_ids": [],
            "party": [
                {
                    "difficulty": 0,
                    "species_id": 412,
                    "form_id": 1,
                    "level": 5,
                    "held_item_id": None,
                    "move_ids": [],
                }
            ]
        }

        trainer = _enrich_trainer(source, pokedb, None, None, engine="gen4_dppt")

        self.assertEqual(
            trainer["party"][0]["pokemon"]["name"], "Burmy (Sandy Cloak)"
        )

    def test_enriches_and_renders_a_trainer_party(self) -> None:
        source = {
            "trainer_id": 0,
            "name": "Tristan",
            "class_id": 2,
            "class_name": "Youngster",
            "class_gender": "male",
            "has_custom_moves": True,
            "has_held_items": True,
            "unknown_byte": 0,
            "party_count": 1,
            "reward_item_ids": [0, 0, 0, 0],
            "ai_flags": 0,
            "battle_type": 0,
            "double_battle": False,
            "party": [{
                "difficulty": 0,
                "gender_ability": 0,
                "level": 5,
                "species_id": 1,
                "form_id": 0,
                "held_item_id": 1,
                "move_ids": [33, 0, 0, 0],
                "ball_seal": 0,
            }],
            "trailing_party_data": "",
            "provenance": {"source": "rom", "archive": "trdata.narc", "member": 0},
            "party_provenance": {"source": "rom", "archive": "trpoke.narc", "member": 0},
            "locations": [{
                "header_id": 343,
                "internal_name": "R202",
                "location_name_id": 17,
                "name": "Route 202",
                "event_file_id": 329,
                "object_index": 0,
                "object_local_id": 0,
                "script_id": 3000,
                "trainer_type": 1,
                "x": 181,
                "y": 65536,
                "z": 818,
            }],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "master-ball"},
            moves_by_id={33: "tackle"},
        )
        move_names = ["None", *(f"Move {move_id}" for move_id in range(1, 468))]
        move_names[33] = "Play Rough"
        enriched = enrich_trainer_dataset(
            {
                "game": "test",
                "engine": "gen4_dppt",
                "source": {},
                "move_names": move_names,
                "records": [source],
            },
            pokedb,
            pokemon_dataset={
                "game": "test",
                "records": [
                    {
                        "member": 1,
                        "name": "Bulbasaur",
                        "slug": "bulbasaur",
                        "sprite": {"url": "https://example.test/bulbasaur.png"},
                        "gender_ratio": 31,
                        "base_stats": {
                            "hp": 45,
                            "attack": 49,
                            "defense": 49,
                            "special_attack": 65,
                            "special_defense": 65,
                            "speed": 45,
                        },
                        "types": [
                            {"id": 12, "name": "grass"},
                            {"id": 3, "name": "poison"},
                        ],
                        "abilities": [
                            {"id": 65, "name": "Overgrow", "slug": "overgrow"},
                            {"id": 34, "name": "Chlorophyll", "slug": "chlorophyll"},
                        ],
                    }
                ],
            },
            move_dataset={
                "game": "test",
                "records": [
                    {
                        "move_id": 33,
                        "type": {"id": 0, "name": "normal"},
                        "damage_class": {"id": 0, "name": "physical"},
                    }
                ],
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "trainer-9999.md"
            stale_page.parent.mkdir(parents=True, exist_ok=True)
            stale_page.write_text("stale", encoding="utf-8")
            count = render_trainer_pages(enriched, output)
            page = (output / "trainer-0000.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(enriched["party_schema_version"], 3)
        self.assertFalse(stale_page.exists())
        self.assertIn("# Youngster Tristan", page)
        self.assertIn('href="../../pokemon/bulbasaur/">Bulbasaur</a>', page)
        self.assertIn('src="https://example.test/bulbasaur.png"', page)
        self.assertIn('width="48" height="48" loading="lazy"', page)
        self.assertIn("Master Ball", page)
        self.assertIn("Play Rough", page)
        self.assertIn("rw-type--grass", page)
        self.assertIn("rw-type--poison", page)
        self.assertIn("rw-type--normal", page)
        self.assertIn("rw-class--physical", page)
        self.assertIn('<span class="rw-party-card__level">Lv. 5</span>', page)
        self.assertIn('<dt>Nature</dt><dd>Timid</dd>', page)
        self.assertIn('aria-label="Male" title="Male">♂</span>', page)
        self.assertIn(
            "| [Route 202](../locations/header-343.md) | 343 | `R202` | "
            "(181, 818) | `329:0` |",
            page,
        )
        self.assertEqual(catalog["kind"], "trainers")
        self.assertEqual(catalog["records"][0]["min_level"], 5)
        party_member = enriched["records"][0]["party"][0]
        self.assertEqual(party_member["moves_source"], "explicit")
        self.assertEqual(party_member["pokemon"]["types"][0]["name"], "grass")
        self.assertEqual(party_member["moves"][0]["type"]["name"], "normal")
        self.assertEqual(
            party_member["moves"][0]["damage_class"]["name"], "physical"
        )
        self.assertEqual(
            party_member["source_fields"],
            {"difficulty": 0, "gender_ability": 0, "ball_seal": 0},
        )
        self.assertNotIn("difficulty", party_member)
        self.assertEqual(
            party_member["ability"],
            {
                "id": 65,
                "name": "Overgrow",
                "slug": "overgrow",
                "slot": 1,
                "source": "derived",
            },
        )
        self.assertEqual(party_member["ivs"]["values"]["speed"], 0)
        self.assertEqual(set(party_member["evs"]["values"].values()), {0})
        self.assertEqual(party_member["nature"]["name"], "Timid")
        self.assertEqual(party_member["gender"]["name"], "Male")
        self.assertEqual(
            party_member["calculated_stats"]["values"],
            {
                "hp": 19,
                "attack": 8,
                "defense": 9,
                "special_attack": 11,
                "special_defense": 11,
                "speed": 9,
            },
        )
        self.assertEqual(
            catalog["records"][0]["party"],
            [{
                "name": "Bulbasaur",
                "level": 5,
                "pokemon_ref": {
                    "kind": "pokemon",
                    "id": 1,
                    "label": "Bulbasaur",
                    "url": "../pokemon/bulbasaur/",
                },
            }],
        )
        self.assertEqual(
            catalog["records"][0]["location_refs"][0]["url"],
            "../locations/header-343/",
        )


if __name__ == "__main__":
    unittest.main()
