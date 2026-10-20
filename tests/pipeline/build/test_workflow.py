from __future__ import annotations

import unittest
from collections.abc import Callable
from functools import partial
from typing import Any
from unittest.mock import Mock, patch

from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.util.errors import DataSourceError, ProfileError


def _recording(
    calls: list[str], label: str, build: Callable[[], dict[str, Any]]
) -> Callable[[], dict[str, Any]]:
    """A side effect that records `label` before building its dataset."""

    def effect() -> dict[str, Any]:
        calls.append(label)
        return build()

    return effect


class GameBuildWorkflowTests(unittest.TestCase):
    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_builds_baseline_before_current_and_compares_results(
        self, context_type: Mock
    ) -> None:
        calls: list[str] = []
        current_context = Mock()
        baseline_context = Mock()
        current_context.profile = _profile("hack")
        baseline_context.profile = _profile("base")
        current_context.moves.side_effect = _recording(
            calls, "current", lambda: _moves("hack", 60)
        )
        baseline_context.moves.side_effect = _recording(
            calls, "baseline", lambda: _moves("base", 50)
        )
        context_type.side_effect = [current_context, baseline_context]
        current = _inspection("hack")
        baseline = _inspection("base")
        workflow = GameBuildWorkflow(current, Mock(), baseline=baseline)

        with self.assertLogs("romwiki", level="INFO") as logs:
            result = workflow.build("moves")

        self.assertEqual(calls, ["baseline", "current"])
        self.assertEqual(result.comparison["counts"]["changed"], 1)
        self.assertIn("Preparing moves dataset for base", "\n".join(logs.output))
        self.assertIn("Preparing moves dataset for hack", "\n".join(logs.output))

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_hack_only_build_has_no_baseline_or_comparison(
        self, context_type: Mock
    ) -> None:
        context = Mock()
        context.profile = _profile("hack")
        context.moves.return_value = _moves("hack", 60)
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("hack"), Mock())

        result = workflow.build("moves")

        self.assertIsNone(result.baseline)
        self.assertIsNone(result.comparison)

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_full_build_finishes_baseline_phase_before_current_phase(
        self, context_type: Mock
    ) -> None:
        calls: list[str] = []
        current_context = Mock()
        baseline_context = Mock()
        current_context.profile = _profile("hack", optional=True)
        baseline_context.profile = _profile("base", optional=True)
        for kind in (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "trainers",
            "locations",
        ):
            getattr(current_context, kind).side_effect = _recording(
                calls, f"current:{kind}", partial(_empty_dataset, kind, "hack")
            )
            getattr(baseline_context, kind).side_effect = _recording(
                calls, f"baseline:{kind}", partial(_empty_dataset, kind, "base")
            )
        context_type.side_effect = [current_context, baseline_context]
        workflow = GameBuildWorkflow(
            _inspection("hack"), Mock(), baseline=_inspection("base")
        )

        workflow.build_all()

        self.assertTrue(all(call.startswith("baseline:") for call in calls[:7]))
        self.assertTrue(all(call.startswith("current:") for call in calls[7:]))

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_full_build_omits_disabled_optional_sections(
        self, context_type: Mock
    ) -> None:
        context = Mock()
        context.profile = _profile("partial")
        for kind in ("pokemon", "abilities", "moves", "items", "encounters"):
            getattr(context, kind).return_value = _empty_dataset(kind, "partial")
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("partial"), Mock())

        builds = workflow.build_all()

        self.assertEqual(
            tuple(builds),
            ("pokemon", "abilities", "moves", "items", "encounters"),
        )
        context.trainers.assert_not_called()
        context.locations.assert_not_called()

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_missing_required_section_has_profile_focused_error(
        self, context_type: Mock
    ) -> None:
        context = Mock()
        context.profile = _profile("partial")
        del context.profile.layout["encounters"]
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("partial"), Mock())

        with self.assertRaisesRegex(
            ProfileError,
            "Profile 'partial'.*encounters requires encounters",
        ):
            workflow.build_all()

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_enabled_section_cannot_return_none(self, context_type: Mock) -> None:
        context = Mock()
        context.profile = _profile("complete", optional=True)
        context.locations.return_value = None
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("complete"), Mock())

        with self.assertRaisesRegex(
            ProfileError,
            "enables 'locations'.*returned no dataset",
        ):
            workflow.build("locations")

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_explicit_build_rejects_disabled_optional_section(
        self, context_type: Mock
    ) -> None:
        context = Mock()
        context.profile = _profile("partial")
        context_type.return_value = context
        workflow = GameBuildWorkflow(_inspection("partial"), Mock())

        with self.assertRaisesRegex(DataSourceError, "does not enable.*trainers"):
            workflow.build("trainers")

    @patch("romwiki.pipeline.build.workflow.GameBuildContext")
    def test_comparative_build_rejects_mismatched_optional_sections(
        self, context_type: Mock
    ) -> None:
        current_context = Mock()
        baseline_context = Mock()
        current_context.profile = _profile("hack", optional=True)
        baseline_context.profile = _profile("base")
        context_type.side_effect = [current_context, baseline_context]
        workflow = GameBuildWorkflow(
            _inspection("hack"), Mock(), baseline=_inspection("base")
        )

        with self.assertRaisesRegex(
            ProfileError,
            "different dataset sections.*base omits locations, trainers",
        ):
            workflow.build_all()


def _inspection(profile_id: str) -> Mock:
    result = Mock()
    result.match.profile.id = profile_id
    return result


def _profile(profile_id: str, *, optional: bool = False) -> Mock:
    profile = Mock()
    profile.id = profile_id
    profile.parameters = {}
    profile.layout = {
        "personal": "personal",
        "messages": "messages",
        "moves": "moves",
        "item_data": "items",
        "encounters": "encounters",
        **(
            {
                "trainer_data": "trainers",
                "trainer_parties": "parties",
                "map_matrices": "maps",
            }
            if optional
            else {}
        ),
    }
    return profile


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
