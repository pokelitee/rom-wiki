from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.dispatcher import extract_location_dataset
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import DataSourceError, ProfileError


def _profile(engine: str) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine=engine,
        base_game="test",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
    )


def _result(engine: str) -> InspectionResult:
    profile = _profile(engine)
    match = HashMatch(
        profile=profile,
        known_hash=KnownHash(algorithm="sha256", value="x", variant="v"),
    )
    return InspectionResult(image=Mock(), match=match)


class LocationDatasetDispatchTests(unittest.TestCase):
    def test_raises_when_no_profile_matched(self) -> None:
        result = InspectionResult(image=Mock(), match=None)

        with self.assertRaises(ProfileError):
            extract_location_dataset(result)

    def test_dispatches_archive_encounter_map_engines(self) -> None:
        result = _result("gen5_bw")
        with (
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher.get_engine",
                return_value=SimpleFormatEngine("archive-encounter-map"),
            ),
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher."
                "extract_archive_encounter_map_location_dataset",
                return_value={"dataset": "locations"},
            ) as archive_extractor,
        ):
            dataset = extract_location_dataset(
                result, "trainers", "static", "items", "marts", "trades"
            )

        self.assertEqual(dataset, {"dataset": "locations"})
        archive_extractor.assert_called_once_with(
            result, "trainers", "static", "items", "marts", "trades"
        )

    def test_dispatches_arm9_encounter_map_engines(self) -> None:
        result = _result("gen4_hgss")
        with (
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher.get_engine",
                return_value=SimpleFormatEngine("arm9-encounter-map"),
            ),
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher."
                "extract_arm9_encounter_map_location_dataset",
                return_value={"dataset": "locations"},
            ) as arm9_extractor,
        ):
            dataset = extract_location_dataset(
                result, trainer_dataset="trainers", item_dataset="items"
            )

        self.assertEqual(dataset, {"dataset": "locations"})
        arm9_extractor.assert_called_once_with(
            result, trainer_dataset="trainers", item_dataset="items"
        )

    def test_dispatches_arm9_event_map_engines(self) -> None:
        result = _result("gen4_platinum")
        with (
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher.get_engine",
                return_value=SimpleFormatEngine("arm9-event-map"),
            ),
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher."
                "extract_arm9_event_map_location_dataset",
                return_value={"dataset": "locations"},
            ) as event_extractor,
        ):
            dataset = extract_location_dataset(
                result, "trainers", "static", "items", "marts", "trades"
            )

        self.assertEqual(dataset, {"dataset": "locations"})
        event_extractor.assert_called_once_with(
            result, "trainers", "static", "items", "marts", "trades"
        )

    def test_raises_for_an_unsupported_extraction_format(self) -> None:
        result = _result("gen4_platinum")
        with (
            patch(
                "romwiki.pipeline.extraction.locations.dispatcher.get_engine",
                return_value=SimpleFormatEngine("unsupported"),
            ),
            self.assertRaisesRegex(DataSourceError, "unsupported"),
        ):
            extract_location_dataset(result)


def SimpleFormatEngine(location_extraction: str) -> SimpleNamespace:
    return SimpleNamespace(
        formats=SimpleNamespace(location_extraction=location_extraction)
    )


if __name__ == "__main__":
    unittest.main()
