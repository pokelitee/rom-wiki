from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import romwiki.engines.gen4.dppt as gen4_dppt
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.learnsets import extract_learnset_dataset
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import ProfileError


class LearnsetDatasetTests(unittest.TestCase):
    def test_requires_a_matched_profile(self) -> None:
        result = InspectionResult(image=Mock(), match=None)

        with self.assertRaisesRegex(ProfileError, "known game profile is required"):
            extract_learnset_dataset(result)

    def test_requires_a_configured_learnset_archive(self) -> None:
        profile = replace(_profile(), layout={})
        result = _result(profile)

        with self.assertRaisesRegex(
            ProfileError, "does not define a level-up learnset archive"
        ):
            extract_learnset_dataset(result)

    def test_extracts_learnset_records(self) -> None:
        profile = _profile()
        result = _result(profile)

        archive = Mock()
        archive.members = [SimpleNamespace(index=0), SimpleNamespace(index=1)]
        archive.read.side_effect = [b"raw-0", b"raw-1"]
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = archive
        filesystem = Mock()
        filesystem.read.return_value = b"learnsets-archive-bytes"
        platform = SimpleNamespace(
            filesystem_from_image=Mock(return_value=filesystem),
            archive_cls=archive_cls,
        )

        record_0 = Mock(to_dict=Mock(return_value={"species_id": 0, "moves": []}))
        record_1 = Mock(to_dict=Mock(return_value={"species_id": 1, "moves": []}))

        with (
            patch(
                "romwiki.pipeline.extraction.learnsets.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_level_up_learnset",
                side_effect=[record_0, record_1],
            ) as parse_learnset,
        ):
            dataset = extract_learnset_dataset(result)

        archive_cls.from_bytes.assert_called_once_with(
            b"learnsets-archive-bytes",
            allow_truncated=False,
            allow_incorrect_data_block_size=False,
            allow_trailing_data=False,
        )
        parse_learnset.assert_any_call(
            b"raw-0", species_id=0, archive_path="learnsets.narc"
        )
        parse_learnset.assert_any_call(
            b"raw-1", species_id=1, archive_path="learnsets.narc"
        )
        self.assertEqual(dataset["dataset"], "level_up_learnsets")
        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(
            dataset["records"],
            [
                {"species_id": 0, "moves": []},
                {"species_id": 1, "moves": []},
            ],
        )
        self.assertEqual(
            dataset["source"],
            {"rom_sha256": "deadbeef", "archive": "learnsets.narc"},
        )

    def test_forwards_truncation_parameters_to_the_archive_reader(self) -> None:
        profile = replace(
            _profile(),
            parameters={
                "learnsets_allow_truncated": True,
                "learnsets_allow_incorrect_data_block_size": True,
                "learnsets_allow_trailing_data": True,
            },
        )
        result = _result(profile)

        archive = Mock()
        archive.members = []
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = archive
        filesystem = Mock()
        filesystem.read.return_value = b"learnsets-archive-bytes"
        platform = SimpleNamespace(
            filesystem_from_image=Mock(return_value=filesystem),
            archive_cls=archive_cls,
        )

        with patch(
            "romwiki.pipeline.extraction.learnsets.get_platform",
            return_value=platform,
        ):
            extract_learnset_dataset(result)

        archive_cls.from_bytes.assert_called_once_with(
            b"learnsets-archive-bytes",
            allow_truncated=True,
            allow_incorrect_data_block_size=True,
            allow_trailing_data=True,
        )

    def test_limits_records_to_the_engines_personal_record_count(self) -> None:
        profile = _profile()
        result = _result(profile)

        archive = Mock()
        archive.members = [
            SimpleNamespace(index=0),
            SimpleNamespace(index=1),
            SimpleNamespace(index=2),
        ]
        archive.read.side_effect = [b"raw-0", b"raw-1"]
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = archive
        filesystem = Mock()
        filesystem.read.return_value = b"learnsets-archive-bytes"
        platform = SimpleNamespace(
            filesystem_from_image=Mock(return_value=filesystem),
            archive_cls=archive_cls,
        )

        record_0 = Mock(to_dict=Mock(return_value={"species_id": 0}))
        record_1 = Mock(to_dict=Mock(return_value={"species_id": 1}))
        fake_adapter = SimpleNamespace(
            personal=SimpleNamespace(PERSONAL_RECORD_COUNT=2),
            learnsets=gen4_dppt,
        )

        with (
            patch(
                "romwiki.pipeline.extraction.learnsets.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.learnsets.get_engine",
                return_value=fake_adapter,
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_level_up_learnset",
                side_effect=[record_0, record_1],
            ) as parse_learnset,
        ):
            dataset = extract_learnset_dataset(result)

        self.assertEqual(parse_learnset.call_count, 2)
        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["records"], [{"species_id": 0}, {"species_id": 1}])


def _profile() -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen4_dppt",
        base_game="platinum",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
        layout={"learnsets": "learnsets.narc"},
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
