from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from romwiki.pipeline.game_build import GameBuildWorkflow


class GameBuildWorkflowTests(unittest.TestCase):
    @patch("romwiki.pipeline.game_build.GameBuildContext")
    def test_builds_baseline_before_current_and_compares_results(
        self, context_type: Mock
    ) -> None:
        calls = []
        current_context = Mock()
        baseline_context = Mock()
        current_context.moves.side_effect = lambda: (
            calls.append("current") or _moves("hack", 60)
        )
        baseline_context.moves.side_effect = lambda: (
            calls.append("baseline") or _moves("base", 50)
        )
        context_type.side_effect = [current_context, baseline_context]
        current = _inspection("hack")
        baseline = _inspection("base")
        workflow = GameBuildWorkflow(current, Mock(), baseline=baseline)

        result = workflow.build("moves")

        self.assertEqual(calls, ["baseline", "current"])
        self.assertEqual(result.comparison["counts"]["changed"], 1)

    @patch("romwiki.pipeline.game_build.GameBuildContext")
    def test_hack_only_build_has_no_baseline_or_comparison(
        self, context_type: Mock
    ) -> None:
        context = Mock()
        context.moves.return_value = _moves("hack", 60)
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("hack"), Mock())

        result = workflow.build("moves")

        self.assertIsNone(result.baseline)
        self.assertIsNone(result.comparison)

    @patch("romwiki.pipeline.game_build.GameBuildContext")
    def test_full_build_finishes_baseline_phase_before_current_phase(
        self, context_type: Mock
    ) -> None:
        calls = []
        current_context = Mock()
        baseline_context = Mock()
        for kind in (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "trainers",
            "locations",
        ):
            getattr(current_context, kind).side_effect = lambda kind=kind: (
                calls.append(f"current:{kind}") or _empty_dataset(kind, "hack")
            )
            getattr(baseline_context, kind).side_effect = lambda kind=kind: (
                calls.append(f"baseline:{kind}") or _empty_dataset(kind, "base")
            )
        context_type.side_effect = [current_context, baseline_context]
        workflow = GameBuildWorkflow(
            _inspection("hack"), Mock(), baseline=_inspection("base")
        )

        workflow.build_all()

        self.assertTrue(all(call.startswith("baseline:") for call in calls[:7]))
        self.assertTrue(all(call.startswith("current:") for call in calls[7:]))


def _inspection(profile_id: str) -> Mock:
    result = Mock()
    result.match.profile.id = profile_id
    return result


def _moves(game: str, power: int) -> dict:
    return {
        "schema_version": 1,
        "dataset": "moves",
        "game": game,
        "source": {"rom_sha256": game},
        "records": [
            {
                "move_id": 1,
                "name": "Pound",
                "slug": "pound",
                "type": {"id": 0, "name": "normal"},
                "damage_class": "physical",
                "power": power,
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
        ],
    }


def _empty_dataset(kind: str, game: str) -> dict:
    dataset_kind = "wild_encounters" if kind == "encounters" else kind
    return {
        "schema_version": 1,
        "dataset": dataset_kind,
        "game": game,
        "source": {"rom_sha256": game},
        "records": [],
    }


if __name__ == "__main__":
    unittest.main()
