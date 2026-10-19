from __future__ import annotations

import copy
import unittest
from typing import Any

from romwiki.pipeline.build.checks import check_game_datasets, find_dataset_problems
from romwiki.util.errors import DataSourceError

_STATS = {
    "hp": 45,
    "attack": 49,
    "defense": 49,
    "special_attack": 65,
    "special_defense": 65,
    "speed": 45,
}


def _pokemon(member: int, slug: str, dex: int | None, **fields: Any) -> dict[str, Any]:
    return {
        "member": member,
        "slug": slug,
        "name": slug.title(),
        "national_dex_id": dex,
        "form": None,
        "public": True,
        "base_stats": dict(_STATS),
        "level_up_moves": [{"level": 1, "move": {"id": 33, "slug": "tackle"}}],
        "evolutions": [],
        **fields,
    }


def _datasets() -> dict[str, dict[str, Any]]:
    return {
        "pokemon": {
            "supplemental_sources": {"level_up_learnsets": {}},
            "records": [
                _pokemon(0, "none", None, public=False),
                _pokemon(
                    1,
                    "bulbasaur",
                    1,
                    evolutions=[{"target": {"id": 2, "slug": "ivysaur"}}],
                ),
                _pokemon(2, "ivysaur", 2),
            ],
        },
        "moves": {"records": [{"move_id": 33, "slug": "tackle"}]},
        "items": {"records": [{"item_id": 1, "slug": "master-ball"}]},
        "abilities": {"records": [{"ability_id": 65, "slug": "overgrow"}]},
        "trainers": {
            "records": [
                {"trainer_id": 1, "party": [{"pokemon": {"slug": "bulbasaur"}}]}
            ]
        },
    }


class DatasetCheckTests(unittest.TestCase):
    def assert_problem(self, datasets: dict[str, Any], expected: str) -> None:
        problems = find_dataset_problems(datasets)
        self.assertTrue(
            any(expected in problem for problem in problems),
            f"{expected!r} not reported in {problems}",
        )

    def test_consistent_datasets_pass(self) -> None:
        self.assertEqual(find_dataset_problems(_datasets()), [])
        check_game_datasets("test-game", _datasets())

    def test_non_public_records_are_not_checked(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(
            _pokemon(3, "egg", None, public=False, base_stats={}, name="")
        )

        self.assertEqual(find_dataset_problems(datasets), [])

    def test_reports_duplicate_species(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(_pokemon(252, "ivysaur", 2))

        self.assert_problem(datasets, "pokemon: duplicate slugs (1): ivysaur")
        self.assert_problem(datasets, "duplicate National Dex numbers and forms")

    def test_forms_may_share_a_national_dex_number(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(
            _pokemon(500, "ivysaur-mega", 2, form="mega")
        )

        self.assertEqual(find_dataset_problems(datasets), [])

    def test_reports_national_dex_gaps(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(_pokemon(5, "charmeleon", 5))

        self.assert_problem(datasets, "National Dex numbers missing (2): 3, 4")

    def test_reports_public_records_without_identity(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(_pokemon(3, "mystery", None, name=""))

        self.assert_problem(datasets, "missing names (1): mystery")
        self.assert_problem(datasets, "missing National Dex numbers (1): mystery")

    def test_reports_base_stats_out_of_range(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"][1]["base_stats"]["attack"] = 0

        self.assert_problem(datasets, "base stats out of range (1): bulbasaur")

    def test_requires_level_up_moves_only_when_learnsets_were_extracted(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"][2]["level_up_moves"] = []
        self.assert_problem(datasets, "no level-up moves (1): ivysaur")

        without_learnsets = copy.deepcopy(datasets)
        without_learnsets["pokemon"]["supplemental_sources"] = {}
        self.assertEqual(find_dataset_problems(without_learnsets), [])

    def test_reports_duplicate_record_identities(self) -> None:
        datasets = _datasets()
        datasets["moves"]["records"].append({"move_id": 33, "slug": "tackle"})
        datasets["items"]["records"].append({"item_id": 2, "slug": "master-ball"})

        self.assert_problem(datasets, "moves: duplicate move_id values (1): 33")
        self.assert_problem(datasets, "items: duplicate slugs (1): master-ball")

    def test_reports_references_to_missing_records(self) -> None:
        datasets = _datasets()
        bulbasaur = datasets["pokemon"]["records"][1]
        bulbasaur["evolutions"] = [{"target": {"id": 3, "slug": "venusaur"}}]
        bulbasaur["level_up_moves"].append(
            {"level": 7, "move": {"id": 73, "slug": "leech-seed"}}
        )
        datasets["trainers"]["records"][0]["party"].append(
            {"pokemon": {"slug": "bagon"}}
        )

        self.assert_problem(datasets, "evolution targets not found (1): venusaur")
        self.assert_problem(datasets, "level-up moves not found (1): 73")
        self.assert_problem(datasets, "party Pokémon not found (1): bagon")

    def test_skips_references_to_datasets_that_were_not_built(self) -> None:
        datasets = {"pokemon": _datasets()["pokemon"]}
        datasets["pokemon"]["records"][1]["level_up_moves"].append(
            {"level": 7, "move": {"id": 73, "slug": "leech-seed"}}
        )

        self.assertEqual(find_dataset_problems(datasets), [])

    def test_check_raises_with_every_problem_listed(self) -> None:
        datasets = _datasets()
        datasets["pokemon"]["records"].append(_pokemon(252, "ivysaur", 2))
        datasets["moves"]["records"].append({"move_id": 33, "slug": "tackle"})

        with self.assertRaises(DataSourceError) as raised:
            check_game_datasets("test-game", datasets)

        message = str(raised.exception)
        self.assertIn("test-game datasets failed content checks", message)
        self.assertIn("- pokemon: duplicate slugs", message)
        self.assertIn("- moves: duplicate move_id values", message)


if __name__ == "__main__":
    unittest.main()
