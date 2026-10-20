from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.static_encounters import (
    extract_static_encounter_dataset,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.pokemon import RecordProvenance
from romwiki.schema.static_encounters import StaticEncounter
from romwiki.util.errors import ProfileError


def _profile(**overrides) -> GameProfile:
    fields: dict[str, Any] = {
        "id": "test",
        "name": "Test",
        "platform": "nintendo-ds",
        "engine": "gen5_bw",
        "base_game": "black",
        "game_codes": ("IRBO",),
        "rom_versions": (0,),
        "hashes": (),
        "layout": {"scripts": "scripts.narc"},
        "parameters": {},
    }
    fields.update(overrides)
    return GameProfile(**fields)


def _result(profile: GameProfile | None) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "romsha256"
    match = (
        HashMatch(
            profile=profile,
            known_hash=KnownHash(algorithm="sha256", value="romsha256", variant="v1"),
        )
        if profile
        else None
    )
    return InspectionResult(image=image, match=match)


def _fake_platform(*, archive: SimpleNamespace, filesystem: Mock) -> SimpleNamespace:
    archive_cls = Mock()
    archive_cls.from_bytes = Mock(return_value=archive)
    return SimpleNamespace(
        archive_cls=archive_cls,
        filesystem_from_image=Mock(return_value=filesystem),
    )


def _fake_engine(
    *, static_encounters_format: str = "script-commands", discover=None
) -> SimpleNamespace:
    formats = SimpleNamespace(static_encounters=static_encounters_format)
    concern = SimpleNamespace(
        POKEMON_NAME_COUNT=650,
        ITEM_NAME_COUNT=600,
        discover_static_encounters=discover or Mock(return_value=()),
    )
    return SimpleNamespace(formats=formats, static_encounters=concern)


def _archive(count: int) -> SimpleNamespace:
    return SimpleNamespace(
        members=[SimpleNamespace(index=index) for index in range(count)],
        read=Mock(side_effect=lambda index: f"member-{index}".encode()),
    )


def _encounter(encounter_id: int) -> StaticEncounter:
    return StaticEncounter(
        encounter_id=encounter_id,
        species_id=1,
        level=5,
        is_egg=False,
        provenance=RecordProvenance(source="rom", archive="scripts.narc", member=0),
        command_offset=0x10,
        command="CallWildBattle",
    )


class ExtractStaticEncounterDatasetTests(unittest.TestCase):
    def test_raises_profile_error_without_match(self) -> None:
        with self.assertRaises(ProfileError):
            extract_static_encounter_dataset(_result(None))

    def test_raises_profile_error_without_scripts_layout(self) -> None:
        profile = replace(_profile(), layout={})
        with self.assertRaisesRegex(ProfileError, "static encounter metadata"):
            extract_static_encounter_dataset(_result(profile))

    def test_raises_profile_error_for_unsupported_engine_format(self) -> None:
        profile = _profile()
        filesystem = Mock()
        filesystem.read.return_value = b"scripts-data"
        platform = _fake_platform(archive=_archive(1), filesystem=filesystem)
        engine = _fake_engine(static_encounters_format="none")

        with (
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_engine",
                return_value=engine,
            ),
            self.assertRaisesRegex(
                ProfileError, "does not support static encounter extraction"
            ),
        ):
            extract_static_encounter_dataset(_result(profile))

    def test_success_builds_dataset_envelope_from_discovered_encounters(self) -> None:
        profile = _profile()
        filesystem = Mock()
        filesystem.read.return_value = b"scripts-data"
        archive = _archive(3)
        platform = _fake_platform(archive=archive, filesystem=filesystem)
        encounters = (_encounter(0), _encounter(1))
        discover = Mock(return_value=encounters)
        engine = _fake_engine(discover=discover)

        with (
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_engine",
                return_value=engine,
            ),
        ):
            result = extract_static_encounter_dataset(_result(profile))

        self.assertEqual(result["dataset"], "static_encounters")
        self.assertEqual(result["game"], "test")
        self.assertEqual(result["engine"], "gen5_bw")
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(
            result["source"], {"rom_sha256": "romsha256", "archive": "scripts.narc"}
        )
        self.assertEqual(
            [record["encounter_id"] for record in result["records"]], [0, 1]
        )
        discover.assert_called_once_with(
            archive.read,
            member_count=3,
            archive_path="scripts.narc",
            species_count=650,
            item_count=600,
        )

    def test_passes_archive_truncation_options_from_profile_parameters(self) -> None:
        profile = _profile(
            parameters={
                "field_archives_allow_incorrect_data_block_size": True,
                "field_archives_allow_trailing_data": True,
            }
        )
        filesystem = Mock()
        filesystem.read.return_value = b"scripts-data"
        archive_cls = Mock()
        archive_cls.from_bytes = Mock(return_value=_archive(0))
        platform = SimpleNamespace(
            archive_cls=archive_cls,
            filesystem_from_image=Mock(return_value=filesystem),
        )
        engine = _fake_engine()

        with (
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_engine",
                return_value=engine,
            ),
        ):
            extract_static_encounter_dataset(_result(profile))

        archive_cls.from_bytes.assert_called_once_with(
            b"scripts-data",
            allow_incorrect_data_block_size=True,
            allow_trailing_data=True,
        )

    def test_omits_archive_options_when_not_configured(self) -> None:
        profile = _profile()
        filesystem = Mock()
        filesystem.read.return_value = b"scripts-data"
        archive_cls = Mock()
        archive_cls.from_bytes = Mock(return_value=_archive(0))
        platform = SimpleNamespace(
            archive_cls=archive_cls,
            filesystem_from_image=Mock(return_value=filesystem),
        )
        engine = _fake_engine()

        with (
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.static_encounters.get_engine",
                return_value=engine,
            ),
        ):
            extract_static_encounter_dataset(_result(profile))

        archive_cls.from_bytes.assert_called_once_with(b"scripts-data")


if __name__ == "__main__":
    unittest.main()
