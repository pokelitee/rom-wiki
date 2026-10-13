from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.moves import extract_move_dataset
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import ProfileError


class MoveDatasetTests(unittest.TestCase):
    def test_requires_a_matched_profile(self) -> None:
        result = InspectionResult(image=Mock(), match=None)

        with self.assertRaisesRegex(ProfileError, "known game profile is required"):
            extract_move_dataset(result)

    def test_requires_a_configured_move_archive(self) -> None:
        profile = replace(_profile(), layout={})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "does not define a move archive"):
            extract_move_dataset(result)

    def test_extracts_move_records_and_merges_reference_data(self) -> None:
        profile = _profile()
        result = _result(profile)

        archive = Mock()
        archive.members = [SimpleNamespace(index=0), SimpleNamespace(index=1)]
        archive.read.side_effect = [b"raw-move-0", b"raw-move-1"]
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = archive
        filesystem = Mock()
        filesystem.read.return_value = b"moves-archive-bytes"
        platform = SimpleNamespace(
            filesystem_from_image=Mock(return_value=filesystem),
            archive_cls=archive_cls,
        )

        record_0 = Mock(to_dict=Mock(return_value={"move_id": 0, "name": "Move A"}))
        record_1 = Mock(to_dict=Mock(return_value={"move_id": 1, "name": "Move B"}))

        with (
            patch(
                "romwiki.pipeline.extraction.moves.get_platform",
                return_value=platform,
            ) as get_platform,
            patch(
                "romwiki.engines.gen4.platinum.parse_move_record",
                side_effect=[record_0, record_1],
            ) as parse_move_record,
            patch(
                "romwiki.pipeline.extraction.moves.extract_reference_names",
                return_value={"move_names": ["Move A", "Move B"]},
            ) as extract_names,
            patch(
                "romwiki.pipeline.extraction.moves.extract_reference_descriptions",
                return_value={"move_descriptions": ["Desc A", "Desc B"]},
            ) as extract_descriptions,
        ):
            dataset = extract_move_dataset(result)

        get_platform.assert_called_once_with("nintendo-ds")
        filesystem.read.assert_called_once_with("moves.narc")
        archive_cls.from_bytes.assert_called_once_with(b"moves-archive-bytes")
        parse_move_record.assert_any_call(
            b"raw-move-0", move_id=0, archive_path="moves.narc"
        )
        parse_move_record.assert_any_call(
            b"raw-move-1", move_id=1, archive_path="moves.narc"
        )
        extract_names.assert_called_once_with(profile, filesystem)
        extract_descriptions.assert_called_once_with(
            profile, filesystem, fields={"move_descriptions"}
        )

        self.assertEqual(dataset["dataset"], "moves")
        self.assertEqual(dataset["game"], "test")
        self.assertEqual(dataset["engine"], "gen4_platinum")
        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(
            dataset["records"],
            [
                {"move_id": 0, "name": "Move A"},
                {"move_id": 1, "name": "Move B"},
            ],
        )
        self.assertEqual(
            dataset["source"],
            {"rom_sha256": "deadbeef", "archive": "moves.narc"},
        )
        self.assertEqual(dataset["move_names"], ["Move A", "Move B"])
        self.assertEqual(dataset["move_descriptions"], ["Desc A", "Desc B"])


def _profile() -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen4_platinum",
        base_game="platinum",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
        layout={"moves": "moves.narc"},
        parameters={},
    )


def _result(profile: GameProfile) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "deadbeef"
    known_hash = KnownHash(algorithm="sha256", value="deadbeef", variant="us")
    return InspectionResult(
        image=image, match=HashMatch(profile=profile, known_hash=known_hash)
    )


if __name__ == "__main__":
    unittest.main()
