from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.enrichment.trainers import (
    _default_level_up_move_ids,
    enrich_trainer_dataset,
    enrich_trainer_record,
)
from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_trainer_pages
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError


class TrainerEnrichmentTests(unittest.TestCase):
    def test_derives_the_latest_four_distinct_level_up_moves(self) -> None:
        learnset = [
            {"level": 1, "move": {"id": 10}},
            {"level": 3, "move": {"id": 20}},
            {"level": 5, "move": {"id": 30}},
            {"level": 7, "move": {"id": 40}},
            {"level": 9, "move": {"id": 50}},
            {"level": 10, "move": {"id": 20}},
            {"level": 12, "move": {"id": 60}},
        ]

        self.assertEqual(
            _default_level_up_move_ids(learnset, 10),
            [30, 40, 50, 20],
        )

    def test_labels_burmy_cosmetic_cloaks(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={412: {"id": 412, "name": "burmy", "species": "burmy"}},
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
            ],
        }

        trainer = enrich_trainer_record(
            source, pokedb, None, None, engine="gen4_platinum"
        )

        self.assertEqual(trainer["party"][0]["pokemon"]["name"], "Burmy (Sandy Cloak)")

    def test_falls_back_to_the_base_species_for_an_unrecognized_form_bit(self) -> None:
        # A hack's own trainer data can set a Generation IV form bit for a
        # species that engine's own form tables have no entry for at all
        # (Sacred Gold/Storm Silver's trainer 229 does this for Pinsir,
        # species 127, which has no real Generation IV form). This must
        # resolve to the base species rather than failing the whole build,
        # the same tolerant treatment already given to explicitly
        # cosmetic-only forms.
        pokedb = PokeDBGeneration(
            pokemon_by_id={127: {"id": 127, "name": "Pinsir", "species": "pinsir"}},
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
                    "species_id": 127,
                    "form_id": 1,
                    "level": 5,
                    "held_item_id": None,
                    "move_ids": [],
                }
            ],
        }

        trainer = enrich_trainer_record(source, pokedb, None, None, engine="gen4_hgss")

        self.assertEqual(trainer["party"][0]["pokemon"]["name"], "Pinsir")

    def test_raises_for_an_unrecognized_form_bit_on_a_species_with_known_forms(
        self,
    ) -> None:
        # Unlike a species with no form table entries at all, a form bit
        # that doesn't match any known entry for a species that *does* have
        # tabulated forms (Deoxys, species 386) is far more likely a
        # parsing bug than deliberate hack data, so it must still fail
        # loudly rather than silently resolving to the base species.
        pokedb = PokeDBGeneration(
            pokemon_by_id={386: {"id": 386, "name": "Deoxys", "species": "deoxys"}},
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
                    "species_id": 386,
                    "form_id": 9,
                    "level": 5,
                    "held_item_id": None,
                    "move_ids": [],
                }
            ],
        }

        with self.assertRaises(DataSourceError):
            enrich_trainer_record(source, pokedb, None, None, engine="gen4_platinum")

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
            "party": [
                {
                    "difficulty": 0,
                    "gender_ability": 0,
                    "level": 5,
                    "species_id": 1,
                    "form_id": 0,
                    "held_item_id": 1,
                    "move_ids": [33, 0, 0, 0],
                    "ball_seal": 0,
                }
            ],
            "trailing_party_data": "",
            "provenance": {"source": "rom", "archive": "trdata.narc", "member": 0},
            "party_provenance": {
                "source": "rom",
                "archive": "trpoke.narc",
                "member": 0,
            },
            "locations": [
                {
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
                }
            ],
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
                "engine": "gen4_platinum",
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
                        "slug": "tackle",
                        "type": {"id": 0, "name": "normal"},
                        "damage_class": {"id": 0, "name": "physical"},
                    }
                ],
            },
        )
        enriched["features"] = []
        relationships = build_relationship_index(
            {
                "locations": {
                    "game": "test",
                    "records": [
                        {
                            "header_id": 343,
                            "name": "Route 202",
                            "section_name": "Route 202 south",
                        }
                    ],
                }
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            stale_page = output / "trainer-9999.md"
            stale_page.parent.mkdir(parents=True, exist_ok=True)
            stale_page.write_text("stale", encoding="utf-8")
            count = render_trainer_pages(enriched, output, relationships=relationships)
            page = (output / "trainer-0000.md").read_text(encoding="utf-8")
            index = (output / "index.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(enriched["party_schema_version"], 6)
        self.assertFalse(stale_page.exists())
        self.assertIn("# Youngster Tristan", page)
        self.assertNotIn("Trainer location coverage", index)
        self.assertNotIn("Trainer variant coverage", index)
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
        self.assertIn("<dt>Nature</dt><dd>Timid</dd>", page)
        self.assertIn('aria-label="Male" title="Male">♂</span>', page)
        self.assertIn(
            '<tr><td><a href="../../locations/header-343/">Route 202</a></td>'
            "<td><code>header-343</code></td><td><code>R202</code></td>"
            "<td>(181, 818)</td><td><code>329:0</code></td></tr>",
            page,
        )
        self.assertNotIn("<dt>After victory</dt>", page)
        self.assertNotIn("<dt>Victory item</dt>", page)
        self.assertEqual(catalog["kind"], "trainers")
        self.assertEqual(catalog["records"][0]["route_id"], "trainer-0000")
        self.assertEqual(catalog["records"][0]["min_level"], 5)
        party_member = enriched["records"][0]["party"][0]
        self.assertEqual(party_member["moves_source"], "explicit")
        self.assertEqual(party_member["pokemon"]["types"][0]["name"], "grass")
        self.assertEqual(party_member["moves"][0]["type"]["name"], "normal")
        self.assertEqual(party_member["moves"][0]["damage_class"]["name"], "physical")
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
            [
                {
                    "name": "Bulbasaur",
                    "level": 5,
                    "pokemon_ref": {
                        "kind": "pokemon",
                        "id": 1,
                        "label": "Bulbasaur",
                        "url": "../pokemon/bulbasaur/",
                    },
                }
            ],
        )
        self.assertEqual(
            catalog["records"][0]["location_refs"][0]["url"],
            "../locations/header-343/",
        )


class Gen5TrainerEnrichmentTests(unittest.TestCase):
    def test_resolves_random_selector_when_every_ability_slot_is_identical(
        self,
    ) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 378,
            "class_id": 1,
            "has_custom_moves": False,
            "reward_item_ids": (),
            "party": [
                {
                    "difficulty": 255,
                    "ability_slot": 0,
                    "forced_gender_flag": 0,
                    "level": 54,
                    "species_id": 330,
                    "form_id": 0,
                    "held_item_id": None,
                    "move_ids": (),
                }
            ],
        }
        levitate = {
            "id": 26,
            "name": "Levitate",
            "slug": "levitate",
            "is_hidden": False,
        }
        pokemon_record = {
            "slug": "flygon",
            "name": "Flygon",
            "public": True,
            "base_species": None,
            "gender_ratio": 127,
            "base_stats": dict.fromkeys(
                (
                    "hp",
                    "attack",
                    "defense",
                    "special_attack",
                    "special_defense",
                    "speed",
                ),
                100,
            ),
            "sprite": None,
            "types": [],
            "abilities": [levitate, levitate, {**levitate, "is_hidden": True}],
        }

        trainer = enrich_trainer_record(
            source,
            pokedb,
            None,
            None,
            engine="gen5_b2w2",
            pokemon_records={330: pokemon_record},
        )

        self.assertEqual(
            trainer["party"][0]["ability"],
            {**levitate, "slot": 0, "source": "engine-default"},
        )
        self.assertEqual(trainer["party"][0]["source_fields"]["ability_slot"], 0)

        sand_stream = {
            "id": 45,
            "name": "Sand Stream",
            "slug": "sand-stream",
            "is_hidden": False,
        }
        pokemon_record["abilities"] = [levitate, sand_stream]
        trainer = enrich_trainer_record(
            source,
            pokedb,
            None,
            None,
            engine="gen5_b2w2",
            pokemon_records={330: pokemon_record},
        )

        self.assertEqual(
            trainer["party"][0]["ability"],
            {
                "slot": 0,
                "source": "engine-default",
                "possibilities": [levitate, sand_stream],
            },
        )

    def test_resolves_internal_trainer_species_from_game_data(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 867,
            "class_id": 1,
            "has_custom_moves": False,
            "reward_item_ids": (),
            "party": [
                {
                    "difficulty": 255,
                    "ability_slot": 1,
                    "forced_gender_flag": 0,
                    "level": 48,
                    "species_id": 660,
                    "form_id": 0,
                    "held_item_id": None,
                    "move_ids": (),
                }
            ],
        }
        pokemon_record = {
            "slug": "pokestar-studios-11",
            "name": "Pokestar Studios 11",
            "public": False,
            "base_species": None,
            "gender_ratio": 255,
            "base_stats": {
                "hp": 100,
                "attack": 100,
                "defense": 100,
                "special_attack": 100,
                "special_defense": 100,
                "speed": 100,
            },
            "sprite": None,
            "types": [],
            "abilities": [],
        }

        trainer = enrich_trainer_record(
            source,
            pokedb,
            None,
            None,
            engine="gen5_b2w2",
            pokemon_records={660: pokemon_record},
        )

        self.assertEqual(trainer["party"][0]["pokemon"]["slug"], "pokestar-studios-11")
        self.assertIsNone(trainer["party"][0]["pokemon"]["page_slug"])
        self.assertIsNone(trainer["party"][0]["ability"])

    def test_links_battle_only_forms_to_their_public_base_page(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 1,
            "class_id": 1,
            "has_custom_moves": False,
            "reward_item_ids": (),
            "party": [
                {
                    "difficulty": 0,
                    "ability_slot": 0,
                    "forced_gender_flag": 0,
                    "level": 20,
                    "species_id": 555,
                    "form_id": 1,
                    "held_item_id": None,
                    "move_ids": (),
                }
            ],
        }
        pokemon_record = {
            "slug": "darmanitan-zen",
            "name": "Darmanitan Zen",
            "public": False,
            "base_species": "darmanitan-standard",
            "gender_ratio": 127,
            "base_stats": {
                "hp": 105,
                "attack": 30,
                "defense": 105,
                "special_attack": 140,
                "special_defense": 105,
                "speed": 55,
            },
            "sprite": None,
            "types": [],
            "abilities": [],
        }

        trainer = enrich_trainer_record(
            source,
            pokedb,
            None,
            None,
            engine="gen5_b2w2",
            pokemon_records={"darmanitan-zen": pokemon_record},
        )

        self.assertEqual(
            trainer["party"][0]["pokemon"],
            {
                "id": 555,
                "slug": "darmanitan-standard",
                "name": "Darmanitan Zen",
                "sprite": None,
                "types": [],
            },
        )

    def test_resolves_hack_trainer_forms(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={422: {"id": 422, "name": "shellos", "species": "shellos"}},
            pokemon_by_name={
                "rotom-heat": {
                    "id": 479,
                    "name": "rotom-heat",
                    "species": "rotom",
                }
            },
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 1,
            "class_id": 1,
            "has_custom_moves": False,
            "reward_item_ids": (),
            "party": [
                {
                    "difficulty": 0,
                    "ability_slot": 0,
                    "forced_gender_flag": 0,
                    "level": 20,
                    "species_id": 422,
                    "form_id": 1,
                    "held_item_id": None,
                    "move_ids": (),
                },
                {
                    "difficulty": 0,
                    "ability_slot": 0,
                    "forced_gender_flag": 0,
                    "level": 20,
                    "species_id": 479,
                    "form_id": 1,
                    "held_item_id": None,
                    "move_ids": (),
                },
            ],
        }

        trainer = enrich_trainer_record(source, pokedb, None, None, engine="gen5_bw")

        self.assertEqual(trainer["party"][0]["pokemon"]["name"], "Shellos (East Sea)")
        self.assertEqual(trainer["party"][1]["pokemon"]["name"], "Rotom Heat")

    def test_resolves_redux_cosmetic_trainer_forms(self) -> None:
        pokedb = PokeDBGeneration(
            pokemon_by_id={
                201: {"id": 201, "name": "unown", "species": "unown"},
                618: {"id": 618, "name": "stunfisk", "species": "stunfisk"},
            },
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        source = {
            "trainer_id": 1,
            "class_id": 1,
            "has_custom_moves": False,
            "reward_item_ids": (),
            "party": [
                {
                    "difficulty": 0,
                    "ability_slot": 0,
                    "forced_gender_flag": 0,
                    "level": 41,
                    "species_id": 201,
                    "form_id": 12,
                    "held_item_id": None,
                    "move_ids": (),
                },
                {
                    "difficulty": 255,
                    "ability_slot": 2,
                    "forced_gender_flag": 0,
                    "level": 35,
                    "species_id": 618,
                    "form_id": 5,
                    "held_item_id": None,
                    "move_ids": (),
                },
            ],
        }

        trainer = enrich_trainer_record(source, pokedb, None, None, engine="gen5_b2w2")

        self.assertEqual(trainer["party"][0]["pokemon"]["name"], "Unown (M)")
        self.assertEqual(trainer["party"][1]["pokemon"]["name"], "Stunfisk (Form 5)")

    def test_enriches_and_renders_a_triple_battle_trainer(self) -> None:
        source = {
            "trainer_id": 1,
            "name": "Burgh",
            "class_id": 5,
            "class_name": "Gym Leader",
            "battle_mode": 2,
            "double_battle": False,
            "has_custom_moves": False,
            "has_held_items": False,
            "party_count": 1,
            "reward_item_ids": (0, 0, 0, 0),
            "ai_flags": 0,
            "healer": False,
            "victory_money_multiplier": 30,
            "victory_item_id": 0,
            "party": [
                {
                    "difficulty": 255,
                    "ability_slot": 1,
                    "forced_gender_flag": 2,
                    "level": 20,
                    "species_id": 587,
                    "form_id": 0,
                    "held_item_id": None,
                    "move_ids": [],
                }
            ],
            "provenance": {"source": "rom", "archive": "trdata.narc", "member": 1},
            "party_provenance": {
                "source": "rom",
                "archive": "trpoke.narc",
                "member": 1,
            },
            "locations": (),
            "script_references": (),
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={587: {"id": 587, "name": "emolga", "species": "emolga"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        enriched = enrich_trainer_dataset(
            {
                "game": "test",
                "engine": "gen5_bw",
                "source": {},
                "records": [source],
            },
            pokedb,
        )
        enriched["features"] = ["post-battle-healing", "victory-items"]

        party_member = enriched["records"][0]["party"][0]
        # A forced-female gender flag is stored data, unlike nature/calculated
        # stats, which stay unavailable since Gen V doesn't derive them from a
        # documented, reproducible algorithm the way Gen IV does.
        self.assertEqual(party_member["gender"], {"source": "stored", "name": "Female"})
        self.assertIsNone(party_member["nature"])
        self.assertIsNone(party_member["calculated_stats"])
        self.assertEqual(party_member["ivs"]["values"]["speed"], 31)
        self.assertEqual(
            enriched["records"][0]["base_prize_money"],
            {
                "amount": 2400,
                "final_party_level": 20,
                "multiplier": 30,
                "base_factor": 4,
                "battle_format_multiplier": 1,
                "multiplier_provenance": {
                    "source": "rom",
                    "archive": "trdata.narc",
                    "member": 1,
                    "offset": 17,
                },
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_trainer_pages(enriched, output)
            page = (output / "trainer-0001.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertIn("# Gym Leader Burgh", page)
        self.assertIn("Triple battle", page)
        self.assertEqual(catalog["records"][0]["battle_format"], "triple")
        self.assertIn("Emolga", page)
        self.assertIn("Battle mode", page)
        self.assertNotIn("Battle type", page)
        self.assertIn(
            '<dt>After victory</dt><dd><span class="rw-summary__empty">'
            "No healing</span></dd>",
            page,
        )
        self.assertIn(
            '<dt>Victory item</dt><dd><span class="rw-summary__empty">None</span></dd>',
            page,
        )


if __name__ == "__main__":
    unittest.main()
