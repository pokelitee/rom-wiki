from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trainers.dispatcher import extract_trainer_dataset
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import DataSourceError, ProfileError


class ExtractTrainerDatasetTests(unittest.TestCase):
    def test_requires_a_known_game_profile(self) -> None:
        result = InspectionResult(image=Mock(), match=None)

        with self.assertRaises(ProfileError):
            extract_trainer_dataset(result)

    def test_dispatches_battle_mode_profiles_to_their_extractor(self) -> None:
        profile = _profile(engine="gen5_bw")
        result = InspectionResult(image=Mock(), match=SimpleNamespace(profile=profile))
        engine_adapter = SimpleNamespace(formats=SimpleNamespace(trainers="battle-mode"))

        with (
            patch(
                "romwiki.pipeline.extraction.trainers.dispatcher.get_engine",
                return_value=engine_adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.trainers.battle_mode."
                "extract_battle_mode_trainer_dataset",
                return_value={"dataset": "trainers", "records": []},
            ) as delegate,
        ):
            dataset = extract_trainer_dataset(result)

        delegate.assert_called_once_with(result)
        self.assertEqual(dataset, {"dataset": "trainers", "records": []})

    def test_dispatches_class_gender_profiles_to_their_extractor(self) -> None:
        profile = _profile(engine="gen4_dppt")
        result = InspectionResult(image=Mock(), match=SimpleNamespace(profile=profile))
        engine_adapter = SimpleNamespace(formats=SimpleNamespace(trainers="class-gender"))

        with (
            patch(
                "romwiki.pipeline.extraction.trainers.dispatcher.get_engine",
                return_value=engine_adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.trainers.class_gender."
                "extract_class_gender_trainer_dataset",
                return_value={"dataset": "trainers", "records": ["a"]},
            ) as delegate,
        ):
            dataset = extract_trainer_dataset(result)

        delegate.assert_called_once_with(result)
        self.assertEqual(dataset, {"dataset": "trainers", "records": ["a"]})

    def test_rejects_an_unsupported_trainer_format(self) -> None:
        profile = _profile(engine="unknown")
        result = InspectionResult(image=Mock(), match=SimpleNamespace(profile=profile))
        engine_adapter = SimpleNamespace(formats=SimpleNamespace(trainers="unsupported"))

        with (
            patch(
                "romwiki.pipeline.extraction.trainers.dispatcher.get_engine",
                return_value=engine_adapter,
            ),
            self.assertRaisesRegex(DataSourceError, "Unsupported trainer format"),
        ):
            extract_trainer_dataset(result)


def _profile(*, engine: str) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine=engine,
        base_game="black",
        game_codes=("IRBO",),
        rom_versions=(0,),
        hashes=(),
        layout={},
        parameters={},
    )


if __name__ == "__main__":
    unittest.main()
