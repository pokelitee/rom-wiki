from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.items import build_item_dataset
from romwiki.sources import PokeDBGeneration


class ItemDatasetTests(unittest.TestCase):
    def test_links_hidden_grotto_items_to_the_grottos_own_encounter_route(
        self,
    ) -> None:
        raw = {
            "game": "test",
            "source": {},
            "records": [{**_gen5_item_record(), "item_id": 82}],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        encounters = {
            "game": "test",
            "records": [
                {
                    "area_id": 174,
                    "source_type": "hidden-grotto",
                    "grotto_id": 0,
                    "location": {
                        "header_id": 445,
                        "name": "Floccesy Ranch",
                        "internal_name": "map_445",
                    },
                    "visible_items": [{"item_id": 82, "pool_chance": 1, "group": 0}],
                    "hidden_items": [],
                }
            ],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={82: "fire-stone"},
        )

        record = build_item_dataset(
            raw,
            pokedb,
            pokemon,
            None,
            None,
            encounter_dataset=encounters,
        )["records"][0]

        self.assertEqual(
            record["locations"][0]["encounter_route_key"],
            "hidden-grotto-00",
        )

    def test_preserves_script_award_location_and_quantity(self) -> None:
        raw = {
            "game": "test",
            "source": {},
            "records": [{**_gen5_item_record(), "item_id": 234}],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        locations = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": 67,
                    "name": "Gear Station",
                    "script_awarded_items": [
                        {
                            "item_id": 234,
                            "quantity": 2,
                            "script_file_id": 9,
                            "command_offset": 44,
                        }
                    ],
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

        record = build_item_dataset(raw, pokedb, pokemon, None, locations)["records"][0]

        self.assertEqual(record["locations"][0]["kind"], "script-awarded")
        self.assertEqual(record["locations"][0]["quantity"], 2)
        self.assertIsNone(record["locations"][0]["x"])

    def test_preserves_relationship_source_order_and_deduplicates_trainer_items(
        self,
    ) -> None:
        raw = {
            "game": "test",
            "source": {},
            "records": [{**_gen5_item_record(), "item_id": 234}],
        }
        pokemon_records = []
        for member, name in ((2, "Second"), (1, "First")):
            pokemon_records.append(
                {
                    "public": True,
                    "member": member,
                    "national_dex_id": member,
                    "slug": name.lower(),
                    "name": name,
                    "held_items": [{"id": 234, "rarity": "rare"}],
                    "evolutions": [
                        {
                            "parameter_data": {"kind": "item", "id": 234},
                            "target": {"id": member + 10, "name": f"{name} target"},
                            "method": {"name": "Use item"},
                        }
                    ],
                }
            )
        pokemon = {
            "game": "test",
            "engine": "gen5_bw",
            "source": {},
            "records": pokemon_records,
        }
        trainers = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "trainer_id": trainer_id,
                    "name": f"Trainer {trainer_id}",
                    "class_name": "Ace Trainer",
                    "party": [
                        {
                            "pokemon": {"name": "First", "slug": "first"},
                            "held_item": {"id": 234},
                        }
                    ],
                    "ai_battle_items": [{"id": 234}, {"id": 234}],
                    "victory_item": {"id": 234},
                }
                for trainer_id in (2, 1)
            ],
        }
        locations = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": header_id,
                    "name": f"Location {header_id}",
                    "items": [
                        {"item_id": 234, "kind": "visible", "x": header_id, "z": 0}
                    ],
                    "shops": [
                        {
                            "inventory_id": shop_id,
                            "kind": "specialty",
                            "currency": "money",
                            "dynamic": False,
                            "items": [
                                {
                                    "item_id": 234,
                                    "price": 100,
                                    "required_badges": None,
                                }
                            ],
                        }
                    ],
                    "pokemon_gifts": [
                        {
                            "held_item_id": 234,
                            "species_id": 1,
                            "name": "First",
                        }
                    ],
                    "npc_trades": [
                        {
                            "trade_id": trade_id,
                            "held_item_id": 234,
                            "offered_species_id": 1,
                            "offered_species_name": "First",
                        }
                    ],
                }
                for header_id, shop_id, trade_id in ((20, 3, 5), (10, 4, 6))
            ],
        }
        trades = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "trade_id": trade_id,
                    "held_item_id": 234,
                    "offered_species_id": 1,
                    "offered_forme_id": 0,
                    "ot_name": f"Trader {trade_id}",
                    "nickname": "First",
                }
                for trade_id in (5, 7)
            ],
        }
        marts = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "shop_id": shop_id,
                    "name": f"Shop {shop_id}",
                    "is_main_game": True,
                    "items": [{"item_id": 234}],
                }
                for shop_id in (3, 99)
            ],
        }
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={234: "leftovers"},
        )

        record = build_item_dataset(
            raw,
            pokedb,
            pokemon,
            trainers,
            locations,
            trade_dataset=trades,
            mart_dataset=marts,
        )["records"][0]

        self.assertEqual(
            [reference["name"] for reference in record["wild_held_by"]],
            ["Second", "First"],
        )
        self.assertEqual(
            [reference["source"]["name"] for reference in record["evolutions"]],
            ["Second", "First"],
        )
        for relationship in (
            "trainer_held_by",
            "trainer_battle_items",
            "trainer_rewards",
        ):
            self.assertEqual(
                [reference["trainer_id"] for reference in record[relationship]],
                [2, 1],
            )
        self.assertEqual(
            [reference["header_id"] for reference in record["locations"]],
            [20, 10],
        )
        self.assertEqual(
            [reference.get("header_id") for reference in record["shops"]],
            [20, 10, None],
        )
        self.assertEqual(record["shops"][-1]["shop_id"], 99)
        self.assertEqual(
            [reference["header_id"] for reference in record["gifts"]],
            [20, 10],
        )
        self.assertEqual(
            [reference["trade_id"] for reference in record["trades"]],
            [5, 6, 7],
        )

    def test_builds_item_relationships(self) -> None:
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
                    "victory_item": {
                        "id": 1,
                        "slug": "master-ball",
                        "name": "Master Ball",
                    },
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
                    "section_name": "Route 1 north",
                    "internal_name": "R1",
                    "items": [{"item_id": 1, "kind": "visible", "x": 3, "z": 4}],
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
        self.assertEqual(record["trainer_rewards"][0]["trainer_id"], 2)
        self.assertEqual(record["locations"][0]["name"], "Route 1")

    def test_duplicate_page_slugs_share_the_canonical_item_reference(self) -> None:
        records = []
        for item_id in (628, 629):
            record = _item_record()
            record.update(item_id=item_id, data_archive_member=item_id)
            record["name"] = "DNA Splicers"
            records.append(record)
        raw = {"game": "test", "source": {}, "records": records}
        pokemon = {"game": "test", "source": {}, "records": []}
        pokedb = PokeDBGeneration(
            pokemon_by_id={},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={1: "dna-splicers"},
            items_reference={
                "dna-splicers": {"sprite": "https://example.test/dna-splicers.png"}
            },
        )

        dataset = build_item_dataset(raw, pokedb, pokemon, None, None)

        self.assertEqual(
            [record["slug"] for record in dataset["records"]],
            ["dna-splicers-628", "dna-splicers-629"],
        )
        self.assertTrue(
            all(
                record["reference"]["sprite_url"]
                == "https://example.test/dna-splicers.png"
                for record in dataset["records"]
            )
        )


class FossilRevivalTests(unittest.TestCase):
    def test_resolves_fossil_revival(self) -> None:
        raw = {
            "game": "test",
            "source": {
                "archive": "items.narc",
                "fossil_revival_table": {"member": 877},
            },
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
        locations = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": 21,
                    "name": "Nacrene City",
                    "static_encounters": [
                        {
                            "species_id": 138,
                            "script_file_id": 877,
                        }
                    ],
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
        self.assertEqual(record["revives_into"]["name"], "Omanyte")
        self.assertEqual(record["revives_at"][0]["header_id"], 21)

    def test_attaches_special_vendor_stock_without_a_mart_inventory_id(self) -> None:
        raw = {
            "game": "test",
            "source": {},
            "records": [_gen5_item_record()],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        locations = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": 67,
                    "name": "Gear Station",
                    "shops": [
                        {
                            "inventory_id": None,
                            "selector_id": 254,
                            "kind": "exchange",
                            "currency": "bp",
                            "name": "Battle Point item exchange",
                            "is_main_game": True,
                            "dynamic": False,
                            "items": [
                                {
                                    "item_id": 234,
                                    "price": 48,
                                    "required_badges": None,
                                    "availability": "Weekends",
                                }
                            ],
                        }
                    ],
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

        record = build_item_dataset(raw, pokedb, pokemon, None, locations)["records"][0]

        self.assertEqual(record["shops"][0]["header_id"], 67)
        self.assertEqual(record["shops"][0]["currency"], "bp")
        self.assertEqual(record["shops"][0]["selector_id"], 254)
        self.assertEqual(record["shops"][0]["availability"], "Weekends")


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

    def test_prefers_a_location_linked_gen5_shop_reference(self) -> None:
        raw = {
            "game": "test",
            "source": {"archive": "itemdata.narc"},
            "records": [_gen5_item_record()],
        }
        pokemon = {"game": "test", "source": {}, "records": []}
        mart_dataset = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "shop_id": 13,
                    "name": "Driftveil Incense Salesman",
                    "is_main_game": False,
                    "items": [{"item_id": 234, "name": "Leftovers"}],
                }
            ],
        }
        location_dataset = {
            "game": "test",
            "source": {},
            "records": [
                {
                    "header_id": 105,
                    "name": "Driftveil City",
                    "shops": [
                        {
                            "inventory_id": 13,
                            "kind": "specialty",
                            "currency": "money",
                            "name": "Driftveil Incense Salesman",
                            "is_main_game": False,
                            "dynamic": False,
                            "items": [
                                {
                                    "item_id": 234,
                                    "price": 9600,
                                    "required_badges": None,
                                }
                            ],
                        }
                    ],
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
            raw,
            pokedb,
            pokemon,
            None,
            location_dataset,
            mart_dataset=mart_dataset,
        )

        self.assertEqual(len(dataset["records"][0]["shops"]), 1)
        self.assertEqual(dataset["records"][0]["shops"][0]["header_id"], 105)
        self.assertEqual(
            dataset["records"][0]["shops"][0]["shop_name"],
            "Driftveil Incense Salesman",
        )


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
