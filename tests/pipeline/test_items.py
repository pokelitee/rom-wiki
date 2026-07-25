from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.items import build_item_dataset
from romwiki.renderers.mkdocs import render_item_pages
from romwiki.sources import PokeDBGeneration


class ItemDatasetTests(unittest.TestCase):
    def test_builds_relationships_and_renders_item_page(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "items.narc"},
            "records": [_item_record()],
        }
        pokemon = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "public": True,
                    "member": 1,
                    "national_dex_id": 1,
                    "slug": "bulbasaur",
                    "name": "Bulbasaur",
                    "held_items": [
                        {
                            "rarity": "rare",
                            "id": 1,
                            "slug": "master-ball",
                            "name": "Master Ball",
                        }
                    ],
                    "evolutions": [],
                }
            ],
        }
        trainers = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "trainer_id": 2,
                    "name": "Tristan",
                    "class_name": "Youngster",
                    "party": [
                        {
                            "pokemon": {"name": "Bulbasaur", "slug": "bulbasaur"},
                            "held_item": {
                                "id": 1,
                                "slug": "master-ball",
                                "name": "Master Ball",
                            },
                        }
                    ],
                    "ai_battle_items": [],
                }
            ],
        }
        locations = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": 10,
                    "name": "Route 1",
                    "internal_name": "R1",
                    "items": [
                        {"item_id": 1, "kind": "visible", "x": 3, "z": 4}
                    ],
                    "shops": [],
                    "pokemon_gifts": [],
                    "npc_trades": [],
                }
            ],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "master-ball"},
        )

        dataset = build_item_dataset(raw, pokedb, pokemon, trainers, locations)
        record = dataset["records"][0]
        self.assertEqual(record["slug"], "master-ball")
        self.assertEqual(record["wild_held_by"][0]["name"], "Bulbasaur")
        self.assertEqual(record["trainer_held_by"][0]["trainer_id"], 2)
        self.assertEqual(record["locations"][0]["name"], "Route 1")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_item_pages(dataset, output)
            page = (output / "master-ball.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Master Ball", page)
        self.assertIn("<dt>Item ID</dt><dd>1</dd>", page)
        self.assertIn("<dt>Pocket</dt><dd>Poké Balls</dd>", page)
        self.assertIn("<dt>Base price</dt><dd>₽0</dd>", page)
        self.assertEqual(page.count("<dt>Fling power</dt>"), 1)
        self.assertIn("<dt>Fling effect ID</dt><dd>7</dd>", page)
        self.assertIn("[Route 1](../locations/header-010.md)", page)
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn("trainer-0002.md", page)
        self.assertNotIn("## Shops", page)
        self.assertNotIn("## Gifts and trades", page)
        self.assertNotIn("## Evolutions", page)
        self.assertEqual(catalog["kind"], "items")
        self.assertEqual(
            catalog["records"][0]["features"],
            ["overworld", "wild-held", "trainer-held"],
        )
        self.assertEqual(
            catalog["records"][0]["location_refs"],
            [{
                "kind": "location",
                "id": 10,
                "label": "Route 1",
                "url": "../locations/header-010/",
            }],
        )


class FossilRevivalTests(unittest.TestCase):
    def test_resolves_and_renders_fossil_revival(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "items.narc"},
            "records": [{**_item_record(), "revives_into_species_id": 138}],
        }
        pokemon = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "public": True,
                    "member": 138,
                    "national_dex_id": 138,
                    "slug": "omanyte",
                    "name": "Omanyte",
                    "held_items": [],
                    "evolutions": [],
                }
            ],
        }
        trainers = {"game": "test", "source": {}, "records": []}
        locations = {"game": "test", "source": {}, "records": []}
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "master-ball"},
        )

        dataset = build_item_dataset(raw, pokedb, pokemon, trainers, locations)
        record = dataset["records"][0]
        self.assertEqual(record["revives_into"]["name"], "Omanyte")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_item_pages(dataset, output)
            page = (output / "master-ball.md").read_text(encoding="utf-8")

        self.assertIn("## Fossil revival", page)
        self.assertIn("[Omanyte](../pokemon/omanyte.md)", page)


class BerryMechanicsTests(unittest.TestCase):
    def test_renders_berry_mechanics_section(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "items.narc"},
            "records": [
                {
                    **_item_record(),
                    "item_id": 149,
                    "name": "Cheri Berry",
                    "berry": {
                        "size": 20,
                        "firmness": 2,
                        "firmness_name": "Soft",
                        "base_yield": 1,
                        "stage_duration": 3,
                        "moisture_drain_rate": 15,
                        "spiciness": 10,
                        "dryness": 0,
                        "sweetness": 0,
                        "bitterness": 0,
                        "sourness": 0,
                        "smoothness": 25,
                    },
                }
            ],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        trainers = {"game": "test", "source": {}, "records": []}
        locations = {"game": "test", "source": {}, "records": []}
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={149: "cheri-berry"},
        )

        dataset = build_item_dataset(raw, pokedb, pokemon, trainers, locations)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_item_pages(dataset, output)
            page = (output / "cheri-berry.md").read_text(encoding="utf-8")

        self.assertIn("## Berry mechanics", page)
        self.assertIn("<dt>Firmness</dt><dd>Soft</dd>", page)
        self.assertIn("<dt>Spicy</dt><dd>10</dd>", page)


class MinimalItemDatasetTests(unittest.TestCase):
    def test_degrades_cleanly_without_trainer_and_location_datasets(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "itemdata.narc"},
            "records": [_gen5_item_record()],
        }
        pokemon = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "public": True,
                    "member": 1,
                    "national_dex_id": 1,
                    "slug": "bulbasaur",
                    "name": "Bulbasaur",
                    "held_items": [
                        {
                            "rarity": "rare",
                            "id": 234,
                            "slug": "leftovers",
                            "name": "Leftovers",
                        }
                    ],
                    "evolutions": [],
                }
            ],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={234: "leftovers"},
        )

        dataset = build_item_dataset(raw, pokedb, pokemon, None, None)
        record = dataset["records"][0]
        self.assertEqual(record["slug"], "leftovers")
        self.assertEqual(record["wild_held_by"][0]["name"], "Bulbasaur")
        self.assertIsNone(dataset["supplemental_sources"]["trainers"])
        self.assertIsNone(dataset["supplemental_sources"]["locations"])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_item_pages(dataset, output)
            page = (output / "leftovers.md").read_text(encoding="utf-8")
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertIn("# Leftovers", page)
        self.assertIn("<dt>Held effect ID</dt><dd>69</dd>", page)
        self.assertNotIn("<dt>Pocket</dt>", page)
        self.assertNotIn("Field pocket ID", page)
        self.assertNotIn("Usable on party", page)
        self.assertIsNone(catalog["records"][0]["pocket"])
        self.assertIsNone(catalog["records"][0]["field_use"])

    def test_attaches_a_gen5_shop_cross_reference(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "itemdata.narc"},
            "records": [_gen5_item_record()],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        mart_dataset = {
            "game": "test",
            "source": {"shop_item_overlay": {"id": 21, "file_id": 0}},
            "records": [
                {
                    "shop_id": 13,
                    "name": "Driftveil Incense Salesman",
                    "is_main_game": False,
                    "items": [{"item_id": 234, "name": "Leftovers"}],
                }
            ],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={234: "leftovers"},
        )

        dataset = build_item_dataset(
            raw, pokedb, pokemon, None, None, mart_dataset=mart_dataset
        )
        record = dataset["records"][0]
        self.assertEqual(
            record["shops"],
            [
                {
                    "shop_id": 13,
                    "shop_name": "Driftveil Incense Salesman",
                    "is_main_game": False,
                }
            ],
        )
        self.assertEqual(
            dataset["supplemental_sources"]["marts"], mart_dataset["source"]
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_item_pages(dataset, output)
            page = (output / "leftovers.md").read_text(encoding="utf-8")

        self.assertIn("## Shops", page)
        self.assertIn("Driftveil Incense Salesman", page)
        self.assertIn("Post-game", page)


def _gen5_item_record() -> dict:
    return {
        "item_id": 234,
        "data_archive_member": 234,
        "name": "Leftovers",
        "public": True,
        "price": 4000,
        "hold_effect_id": 69,
        "pluck_effect_id": 0,
        "fling_effect_id": 0,
        "fling_power": 10,
        "revives_into_species_id": None,
        "berry": None,
        "provenance": {"source": "rom", "archive": "itemdata.narc", "member": 234},
    }


def _item_record() -> dict:
    return {
        "item_id": 1,
        "data_archive_member": 1,
        "name": "Master Ball",
        "public": True,
        "price": 0,
        "hold_effect_id": 0,
        "hold_effect_parameter": 0,
        "pluck_effect_id": 0,
        "fling_effect_id": 7,
        "fling_power": 30,
        "natural_gift_power": 0,
        "natural_gift_type_id": 0,
        "natural_gift_type": {"id": 0, "name": "normal"},
        "prevent_toss": False,
        "selectable": True,
        "field_pocket_id": 2,
        "pocket": {"id": 2, "name": "poke-balls"},
        "battle_pocket_mask": 1,
        "field_use_function_id": 0,
        "field_use": {"id": 0, "name": "none"},
        "battle_use_function_id": 0,
        "party_use": False,
        "party_effects": {},
        "provenance": {"source": "rom", "archive": "items.narc", "member": 1},
    }


if __name__ == "__main__":
    unittest.main()
