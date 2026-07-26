from __future__ import annotations

import unittest

from romwiki.pipeline.comparisons import compare_datasets, comparison_by_key
from romwiki.util.errors import DataSourceError


class DatasetComparisonTests(unittest.TestCase):
    def test_classifies_added_removed_changed_and_unchanged_records(self) -> None:
        baseline = _dataset(
            "moves",
            "platinum-us",
            [
                _move(1, "Pound", power=40),
                _move(2, "Karate Chop", power=50),
                _move(3, "Double Slap", power=15),
            ],
        )
        current = _dataset(
            "moves",
            "renegade-platinum",
            [
                _move(1, "Pound", power=40),
                _move(2, "Karate Chop", power=60),
                _move(4, "Comet Punch", power=18),
            ],
        )

        comparison = compare_datasets(current, baseline)
        records = comparison_by_key(comparison)

        self.assertEqual(
            comparison["counts"],
            {"unchanged": 1, "changed": 1, "added": 1, "removed": 1},
        )
        self.assertEqual(records[1]["status"], "unchanged")
        self.assertEqual(records[2]["status"], "changed")
        self.assertEqual(records[2]["changes"][0]["field"], "power")
        self.assertEqual(records[4]["status"], "added")
        self.assertTrue(records[4]["detail_available"])
        self.assertEqual(records[3]["status"], "removed")
        self.assertIn("power", records[3]["baseline_record"])

    def test_ignores_order_for_set_like_relationships_and_provenance(self) -> None:
        first = {"id": 1, "name": "TM01", "provenance": {"offset": 1}}
        second = {"id": 2, "name": "TM02", "provenance": {"offset": 2}}
        baseline = _dataset(
            "moves", "platinum-us", [_move(1, "Pound", machines=[first, second])]
        )
        current = _dataset(
            "moves",
            "renegade-platinum",
            [_move(1, "Pound", machines=[second, first])],
        )

        comparison = compare_datasets(current, baseline)

        self.assertEqual(comparison["counts"]["unchanged"], 1)

    def test_normalizes_tuple_and_list_sequences(self) -> None:
        baseline_record = _move(1, "Pound")
        current_record = _move(1, "Pound")
        baseline_record["machines"] = ()
        current_record["machines"] = []

        comparison = compare_datasets(
            _dataset("moves", "hack", [current_record]),
            _dataset("moves", "base", [baseline_record]),
        )

        self.assertEqual(comparison["counts"]["unchanged"], 1)

    def test_ignores_engine_source_fields_in_trainer_comparisons(self) -> None:
        baseline_member = {
            "pokemon": {"id": 1, "slug": "bulbasaur", "name": "Bulbasaur"},
            "level": 5,
            "moves": [],
            "moves_source": "level-up",
            "source_fields": {"difficulty": 0},
        }
        current_member = {
            **baseline_member,
            "source_fields": {"difficulty": 100},
        }
        baseline = _dataset(
            "trainers",
            "base",
            [{"trainer_id": 1, "name": "Sam", "party": [baseline_member]}],
        )
        current = _dataset(
            "trainers",
            "hack",
            [{"trainer_id": 1, "name": "Sam", "party": [current_member]}],
        )

        comparison = compare_datasets(current, baseline)

        self.assertEqual(comparison["counts"]["unchanged"], 1)

    def test_compares_normalized_trainer_party_attributes(self) -> None:
        baseline_member = {
            "pokemon": {"id": 1, "slug": "bulbasaur", "name": "Bulbasaur"},
            "level": 5,
            "moves": [],
            "moves_source": "level-up",
            "ability": {"id": 65, "name": "Overgrow", "slot": 1},
            "ivs": {"source": "derived", "values": {"hp": 0}},
        }
        current_member = {
            **baseline_member,
            "ivs": {"source": "derived", "values": {"hp": 12}},
        }
        comparison = compare_datasets(
            _dataset(
                "trainers",
                "hack",
                [{"trainer_id": 1, "name": "Sam", "party": [current_member]}],
            ),
            _dataset(
                "trainers",
                "base",
                [{"trainer_id": 1, "name": "Sam", "party": [baseline_member]}],
            ),
        )

        self.assertEqual(comparison["counts"]["changed"], 1)
        self.assertEqual(comparison["records"][0]["changes"][0]["field"], "party")

    def test_nested_reference_names_do_not_create_mechanical_changes(self) -> None:
        baseline = _dataset(
            "pokemon",
            "base",
            [
                {
                    "member": 1,
                    "name": "Bulbasaur",
                    "slug": "bulbasaur",
                    "public": True,
                    "machines": [
                        {
                            "id": 22,
                            "name": "TM22",
                            "move": {"id": 76, "name": "Solarbeam", "slug": "solarbeam"},
                        }
                    ],
                    "egg_moves": [
                        {"id": 320, "name": "Grasswhistle", "slug": "grasswhistle"}
                    ],
                }
            ],
        )
        current = _dataset(
            "pokemon",
            "hack",
            [
                {
                    "member": 1,
                    "name": "Bulbasaur",
                    "slug": "bulbasaur",
                    "public": True,
                    "machines": [
                        {
                            "id": 22,
                            "name": "TM22",
                            "move": {"id": 76, "name": "Solar Beam", "slug": "solar-beam"},
                        }
                    ],
                    "egg_moves": [
                        {"id": 320, "name": "Grass Whistle", "slug": "grass-whistle"}
                    ],
                }
            ],
        )

        comparison = compare_datasets(current, baseline)

        self.assertEqual(comparison["counts"]["unchanged"], 1)

    def test_rejects_mismatched_dataset_kinds(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "same supported kind"):
            compare_datasets(
                _dataset("moves", "hack", []),
                _dataset("pokemon", "base", []),
            )

    def test_labels_prevent_toss_without_inverting_its_meaning(self) -> None:
        baseline = _dataset(
            "items",
            "base",
            [{"item_id": 1, "name": "Item", "prevent_toss": False}],
        )
        current = _dataset(
            "items",
            "hack",
            [{"item_id": 1, "name": "Item", "prevent_toss": True}],
        )

        comparison = compare_datasets(current, baseline)

        change = comparison["records"][0]["changes"][0]
        self.assertEqual(change["label"], "Prevents tossing")
        self.assertEqual((change["before"], change["after"]), (False, True))

    def test_compares_gen5_encounter_methods(self) -> None:
        baseline = {
            "area_id": 1,
            "name": "Route 1",
            "active": True,
            "grass_cave": {"rate": 20, "slots": [{"species_id": 504}]},
        }
        current = {
            **baseline,
            "grass_cave": {"rate": 20, "slots": [{"species_id": 506}]},
        }

        comparison = compare_datasets(
            _dataset("wild_encounters", "hack", [current]),
            _dataset("wild_encounters", "base", [baseline]),
        )

        self.assertEqual(comparison["counts"]["changed"], 1)
        change = comparison["records"][0]["changes"][0]
        self.assertEqual(change["field"], "grass_cave")
        self.assertEqual(change["label"], "Grass/Cave")


def _dataset(kind: str, game: str, records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "dataset": kind,
        "game": game,
        "source": {"rom_sha256": game},
        "records": records,
    }


def _move(move_id: int, name: str, **overrides: object) -> dict:
    record = {
        "move_id": move_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "public": True,
        "type": {"id": 0, "name": "normal"},
        "damage_class": "physical",
        "power": 40,
        "accuracy": 100,
        "pp": 35,
        "priority": 0,
        "effect_id": 0,
        "effect_chance": 0,
        "target_id": 0,
        "flags": [],
        "contest_effect_id": 0,
        "contest_type_id": 0,
        "machines": [],
        "tutors": [],
        "egg_move_pokemon": [],
    }
    record.update(overrides)
    return record


if __name__ == "__main__":
    unittest.main()
