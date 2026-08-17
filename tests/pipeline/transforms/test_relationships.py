from __future__ import annotations

import unittest

from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.util.errors import DataSourceError


class RelationshipIndexTests(unittest.TestCase):
    def test_merges_same_species_method_levels_and_chances(self) -> None:
        index = build_relationship_index(
            _datasets(
                pokemon=[_pokemon(1, "bulbasaur")],
                encounters=[
                    {
                        "area_id": 4,
                        "name": "Route 204",
                        "locations": [{"header_id": 204, "name": "Route 204"}],
                        "walking": {
                            "rate": 20,
                            "slots": [
                                {
                                    "species_id": 1,
                                    "pokemon": {"id": 1, "slug": "bulbasaur"},
                                    "level": 5,
                                    "chance": 20,
                                },
                                {
                                    "species_id": 1,
                                    "pokemon": {"id": 1, "slug": "bulbasaur"},
                                    "level": 7,
                                    "chance": 10,
                                },
                            ],
                        },
                    }
                ],
            )
        )

        references = index.pokemon_wild_encounters["bulbasaur"]
        self.assertEqual(len(references), 1)
        self.assertEqual(
            (
                references[0].minimum_level,
                references[0].maximum_level,
                references[0].chance,
            ),
            (5, 7, 30),
        )

    def test_builds_gen4_wild_trainer_acquisition_and_learner_references(
        self,
    ) -> None:
        datasets = _datasets(
            pokemon=[
                _pokemon(
                    1,
                    "bulbasaur",
                    level_up_moves=[
                        {"level": 7, "move": {"id": 22, "name": "Vine Whip"}}
                    ],
                    machines=[
                        {
                            "id": 19,
                            "item_id": 346,
                            "kind": "tm",
                            "name": "TM19",
                            "move": {"id": 202, "name": "Giga Drain"},
                        }
                    ],
                    static_encounters=[
                        {
                            "level": 10,
                            "command": "WildBattle",
                            "location": None,
                        }
                    ],
                )
            ],
            encounters=[
                {
                    "area_id": 4,
                    "name": "Route 204",
                    "locations": [{"header_id": 204, "name": "Route 204"}],
                    "walking": {
                        "rate": 20,
                        "slots": [
                            {
                                "species_id": 1,
                                "pokemon": {"id": 1, "slug": "bulbasaur"},
                                "level": 5,
                                "chance": 20,
                            }
                        ],
                    },
                    "special": {
                        "swarm": [
                            {
                                "species_id": 1,
                                "pokemon": {"id": 1, "slug": "bulbasaur"},
                                "level": 6,
                                "chance": 10,
                            }
                        ],
                        "day": [],
                        "night": [],
                        "dual_slot": {},
                        "radar": [],
                    },
                }
            ],
            trainers=[
                {
                    "trainer_id": 12,
                    "name": "Sam",
                    "class_name": "Ace Trainer",
                    "locations": [{"header_id": 204, "name": "Route 204"}],
                    "script_references": [],
                    "party": [
                        {
                            "species_id": 1,
                            "level": 8,
                            "pokemon": {"id": 1, "slug": "bulbasaur"},
                            "held_item": {
                                "id": 1,
                                "name": "Master Ball",
                                "slug": "master-ball",
                            },
                        }
                    ],
                }
            ],
            locations=[
                {
                    "header_id": 204,
                    "name": "Route 204",
                    "pokemon_gifts": [{"species_id": 1, "level": 5, "kind": "pokemon"}],
                    "static_encounters": [],
                    "npc_trades": [],
                    "honey_tree": None,
                    "daily_encounter_pool": None,
                }
            ],
        )

        index = build_relationship_index(datasets)

        wild = index.pokemon_wild_encounters["bulbasaur"]
        self.assertEqual(len(wild), 2)
        self.assertEqual(
            [(entry.method, entry.condition) for entry in wild],
            [("Walking", None), ("Walking", "swarm")],
        )
        appearance = index.pokemon_trainers["bulbasaur"][0]
        self.assertEqual(appearance.trainer_id, 12)
        self.assertEqual(appearance.party_position, 1)
        self.assertEqual(appearance.held_item_slug, "master-ball")
        self.assertTrue(appearance.linked)
        acquisition = index.pokemon_acquisition["bulbasaur"]
        self.assertEqual(
            {(entry.kind, entry.location_name) for entry in acquisition},
            {("gift", "Route 204"), ("static", None)},
        )
        self.assertEqual(index.move_level_up_learners[22][0].pokemon_slug, "bulbasaur")
        self.assertEqual(
            (
                index.move_level_up_learners[22][0].pokemon_id,
                index.move_level_up_learners[22][0].pokemon_name,
                index.move_level_up_learners[22][0].pokemon_form,
            ),
            (1, "Bulbasaur", None),
        )
        machine = index.move_machine_learners[202][0]
        self.assertEqual((machine.machine_name, machine.machine_kind), ("TM19", "tm"))

    def test_builds_gen5_form_and_season_references(self) -> None:
        datasets = _datasets(
            pokemon=[
                _pokemon(550, "basculin-red-striped"),
                _pokemon(
                    551,
                    "basculin-blue-striped",
                    national_dex_id=550,
                ),
            ],
            encounters=[
                {
                    "area_id": 8,
                    "map_index": 3,
                    "season": "spring",
                    "name": "Route 1",
                    "location_names": ["Route 1"],
                    "fishing": {
                        "rate": 50,
                        "slots": [
                            {
                                "species_id": 550,
                                "form_id": 1,
                                "pokemon": {
                                    "id": 550,
                                    "slug": "basculin-blue-striped",
                                },
                                "minimum_level": 35,
                                "maximum_level": 55,
                                "chance": 60,
                            }
                        ],
                    },
                },
                {
                    "area_id": 9,
                    "map_index": 3,
                    "season": "summer",
                    "name": "Route 1",
                    "location_names": ["Route 1"],
                    "fishing": {"rate": 0, "slots": []},
                },
            ],
            locations=[
                {
                    "header_id": 6,
                    "name": "Route 1",
                    "section_name": "Route 1 lower path",
                    "encounter_map_index": 3,
                }
            ],
        )

        index = build_relationship_index(datasets)

        wild = index.pokemon_wild_encounters["basculin-blue-striped"]
        self.assertEqual(len(wild), 1)
        self.assertEqual((wild[0].season, wild[0].method), ("spring", "Fishing"))
        self.assertEqual(wild[0].area_name, "Route 1")
        self.assertEqual(wild[0].locations, ((6, "Route 1"),))
        self.assertNotIn("basculin-red-striped", index.pokemon_wild_encounters)
        variants = index.location_encounters[6]
        self.assertEqual(
            [(entry.area_id, entry.season) for entry in variants],
            [(8, "spring"), (9, "summer")],
        )
        self.assertEqual(
            [entry.encounter_route_key for entry in variants],
            ["map-003", "map-003"],
        )
        spring_locations = index.encounter_locations["map-003"]
        self.assertEqual(
            [
                (
                    entry.header_id,
                    entry.location_name,
                    entry.section_name,
                    entry.versions,
                )
                for entry in spring_locations
            ],
            [(6, "Route 1", "Route 1 lower path", ())],
        )
        self.assertEqual(wild[0].encounter_route_key, "map-003")

    def test_preserves_version_variants_and_deduplicates_equal_slots(self) -> None:
        black = {
            "area_id": 1,
            "map_index": 0,
            "season": None,
            "name": "Route 1",
            "location_names": ["Route 1"],
            "grass_cave": {
                "rate": 20,
                "slots": [
                    {
                        "species_id": 1,
                        "pokemon": {"id": 1, "slug": "bulbasaur"},
                        "minimum_level": 2,
                        "maximum_level": 4,
                        "chance": 20,
                    },
                    {
                        "species_id": 1,
                        "pokemon": {"id": 1, "slug": "bulbasaur"},
                        "minimum_level": 2,
                        "maximum_level": 4,
                        "chance": 20,
                    },
                ],
            },
        }
        white = {
            **black,
            "grass_cave": {
                "rate": 20,
                "slots": [
                    {
                        "species_id": 1,
                        "pokemon": {"id": 1, "slug": "bulbasaur"},
                        "minimum_level": 3,
                        "maximum_level": 5,
                        "chance": 20,
                    }
                ],
            },
        }
        datasets = _datasets(
            pokemon=[_pokemon(1, "bulbasaur", versions=["black", "white"])],
            encounters=[
                {
                    **black,
                    "versions": ["black", "white"],
                    "version_variants": {"black": black, "white": white},
                }
            ],
        )

        references = build_relationship_index(datasets).pokemon_wild_encounters[
            "bulbasaur"
        ]

        self.assertEqual(len(references), 2)
        self.assertEqual(
            [
                (value.minimum_level, value.chance, value.versions)
                for value in references
            ],
            [(2, 40, ("black",)), (3, 20, ("white",))],
        )

    def test_combines_versions_for_the_same_location_encounter_variant(self) -> None:
        variant = {
            "area_id": 1,
            "map_index": 0,
            "season": "spring",
            "name": "Route 1",
        }
        index = build_relationship_index(
            _datasets(
                encounters=[
                    {
                        **variant,
                        "versions": ["black", "white"],
                        "version_variants": {
                            "black": variant,
                            "white": variant,
                        },
                    }
                ],
                locations=[
                    {
                        "header_id": 6,
                        "name": "Route 1",
                        "encounter_map_index": 0,
                    }
                ],
            )
        )

        references = index.location_encounters[6]
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].encounter_route_key, "map-000")
        self.assertEqual(references[0].versions, ("black", "white"))
        reverse = index.encounter_locations["map-000"]
        self.assertEqual(len(reverse), 1)
        self.assertEqual(reverse[0].header_id, 6)
        self.assertEqual(reverse[0].versions, ("black", "white"))

    def test_indexes_map_owned_conditional_encounters_by_header(self) -> None:
        records = [
            {
                "area_id": 194,
                "source_type": "daily-swarm",
                "name": "Route 1",
                "location": {"header_id": 6, "name": "Route 1"},
            },
            {
                "area_id": 174,
                "source_type": "hidden-grotto",
                "grotto_id": 3,
                "name": "Route 1",
                "location": {"header_id": 6, "name": "Route 1"},
            },
        ]

        index = build_relationship_index(
            _datasets(
                encounters=records,
                locations=[{"header_id": 6, "name": "Route 1"}],
            )
        )

        self.assertEqual(
            [
                record["source_type"]
                for record in index.location_conditional_encounters[6]
            ],
            ["hidden-grotto", "daily-swarm"],
        )

    def test_indexes_map_owned_conditional_encounters_without_a_locations_dataset(
        self,
    ) -> None:
        # build-encounters supports omitting the locations dataset entirely;
        # map-owned conditional encounters (headbutt/grotto/swarm) still
        # carry their own header_id, so this must not crash trying to look
        # up a location record that was never supplied.
        records = [
            {
                "area_id": 194,
                "source_type": "daily-swarm",
                "name": "Route 1",
                "location": {"header_id": 6, "name": "Route 1"},
            }
        ]

        index = build_relationship_index(_datasets(encounters=records))

        self.assertEqual(
            [
                record["source_type"]
                for record in index.location_conditional_encounters[6]
            ],
            ["daily-swarm"],
        )
        self.assertEqual(index.encounter_locations, {})

    def test_indexes_safari_pokemon_with_anchored_area_routes(self) -> None:
        safari = {
            "area_id": 300,
            "source_type": "safari-zone",
            "safari_area_id": 0,
            "area_name": "Plains",
            "name": "Plains",
            "methods": {
                "grass": {
                    "base_pools": {
                        "morning": [
                            {
                                "species_id": 1,
                                "level": 17,
                                "pokemon": {"id": 1, "slug": "bulbasaur"},
                            }
                        ]
                    },
                    "block_encounters": [],
                }
            },
        }

        index = build_relationship_index(
            _datasets(pokemon=[_pokemon(1, "bulbasaur")], encounters=[safari])
        )

        reference = index.pokemon_wild_encounters["bulbasaur"][0]
        self.assertEqual(reference.encounter_route_key, "safari-zone#plains")
        self.assertEqual(
            (reference.method, reference.condition), ("Grass", "morning; base pool")
        )

    def test_omits_absent_optional_datasets(self) -> None:
        index = build_relationship_index(
            {
                "pokemon": _dataset(
                    "pokemon",
                    [_pokemon(1, "bulbasaur")],
                )
            }
        )

        self.assertEqual(index.pokemon_wild_encounters, {})
        self.assertEqual(index.pokemon_trainers, {})
        self.assertEqual(index.location_encounters, {})
        self.assertEqual(index.encounter_locations, {})

    def test_rejects_an_unmatched_location_encounter_reference(self) -> None:
        with self.assertRaisesRegex(
            DataSourceError,
            r"header 6 -> map 3",
        ):
            build_relationship_index(
                _datasets(
                    locations=[
                        {
                            "header_id": 6,
                            "name": "Route 1",
                            "encounter_map_index": 3,
                        }
                    ]
                )
            )

    def test_indexes_detached_trades_without_inventing_a_location(self) -> None:
        datasets = _datasets(pokemon=[_pokemon(1, "bulbasaur")])
        datasets["trades"] = _dataset(
            "trades",
            [
                {
                    "trade_id": 2,
                    "interaction": "xtransceiver",
                    "ot_name": "Curtis",
                    "offered_pokemon": {
                        "species_id": 1,
                        "slug": "bulbasaur",
                        "name": "Bulbasaur",
                    },
                    "requested_pokemon": {
                        "species_id": 4,
                        "slug": "charmander",
                        "name": "Charmander",
                    },
                }
            ],
        )

        trade = build_relationship_index(datasets).pokemon_acquisition["bulbasaur"][0]

        self.assertEqual(trade.kind, "trade")
        self.assertEqual(trade.detail, "Xtransceiver trade with Curtis for Charmander")
        self.assertIsNone(trade.location_id)
        self.assertIsNone(trade.location_name)

    def test_rejects_datasets_for_different_games(self) -> None:
        datasets = _datasets(pokemon=[_pokemon(1, "bulbasaur")])
        datasets["trainers"] = {
            **datasets["trainers"],
            "game": "another-game",
        }

        with self.assertRaisesRegex(DataSourceError, "same game"):
            build_relationship_index(datasets)

    def test_rejects_invalid_record_collection(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "records must be a list"):
            build_relationship_index(
                {
                    "pokemon": {
                        "dataset": "pokemon",
                        "game": "test-game",
                        "records": {},
                    }
                }
            )


def _datasets(
    *,
    pokemon: list[dict] | None = None,
    encounters: list[dict] | None = None,
    trainers: list[dict] | None = None,
    locations: list[dict] | None = None,
    items: list[dict] | None = None,
) -> dict[str, dict]:
    return {
        "pokemon": _dataset("pokemon", pokemon or []),
        "encounters": _dataset("wild_encounters", encounters or []),
        "trainers": _dataset("trainers", trainers or []),
        "locations": _dataset("locations", locations or []),
        "items": _dataset("items", items or []),
    }


def _dataset(kind: str, records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "dataset": kind,
        "game": "test-game",
        "records": records,
    }


def _pokemon(
    member: int,
    slug: str,
    *,
    national_dex_id: int | None = None,
    **overrides: object,
) -> dict:
    record = {
        "member": member,
        "national_dex_id": national_dex_id or member,
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "public": True,
        "level_up_moves": [],
        "machines": [],
        "static_encounters": [],
    }
    record.update(overrides)
    return record


if __name__ == "__main__":
    unittest.main()
