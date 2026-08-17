from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.tutors import (
    _extract_overlay_archive_tutors,
    _extract_personal_archive_tutors,
    _extract_special_tutors,
    _slice_overlay,
    extract_tutor_dataset,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError

MODULE = "romwiki.pipeline.extraction.tutors"


class DispatchTests(unittest.TestCase):
    def test_requires_a_matched_profile(self) -> None:
        result = InspectionResult(image=Mock(), match=None)

        with self.assertRaisesRegex(ProfileError, "known game profile is required"):
            extract_tutor_dataset(result)

    def test_dispatches_personal_archive_format(self) -> None:
        profile = _profile()
        result = _result(profile)
        adapter = SimpleNamespace(formats=SimpleNamespace(tutors="personal-archive"))

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(
                f"{MODULE}._extract_personal_archive_tutors",
                return_value={"dataset": "move_tutors"},
            ) as helper,
        ):
            dataset = extract_tutor_dataset(result)

        helper.assert_called_once_with(result)
        self.assertEqual(dataset, {"dataset": "move_tutors"})

    def test_dispatches_overlay_archive_format(self) -> None:
        profile = _profile()
        result = _result(profile)
        adapter = SimpleNamespace(formats=SimpleNamespace(tutors="overlay-archive"))

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(
                f"{MODULE}._extract_overlay_archive_tutors",
                return_value={"dataset": "move_tutors"},
            ) as helper,
        ):
            dataset = extract_tutor_dataset(result)

        helper.assert_called_once_with(result)
        self.assertEqual(dataset, {"dataset": "move_tutors"})

    def test_rejects_an_unsupported_tutor_format(self) -> None:
        profile = _profile()
        result = _result(profile)
        adapter = SimpleNamespace(formats=SimpleNamespace(tutors="none"))

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            self.assertRaisesRegex(DataSourceError, "does not provide tutor"),
        ):
            extract_tutor_dataset(result)

    def test_overlay_table_requires_its_profile_parameters(self) -> None:
        profile = replace(_profile(), parameters={})
        result = _result(profile)
        adapter = SimpleNamespace(formats=SimpleNamespace(tutors="overlay-table"))

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            self.assertRaisesRegex(ProfileError, "does not define tutor data"),
        ):
            extract_tutor_dataset(result)

    def test_overlay_table_success_path(self) -> None:
        profile = replace(
            _profile(),
            parameters={
                "tutor_overlay_id": 5,
                "tutor_move_offset": 0,
                "tutor_count": 2,
                "tutor_compatibility_offset": 4,
            },
        )
        result = _result(profile)

        move_1 = SimpleNamespace(
            location_id=0, to_dict=Mock(return_value={"tutor_id": 1})
        )
        move_2 = SimpleNamespace(
            location_id=1, to_dict=Mock(return_value={"tutor_id": 2})
        )
        compat_1 = Mock(to_dict=Mock(return_value={"personal_member": 1}))
        engine = SimpleNamespace(
            TUTOR_RECORD_SIZE=2,
            TUTOR_COMPATIBILITY_RECORD_SIZE=1,
            FORM_MEMBERS=frozenset({10}),
            BASE_SPECIES_COUNT=3,
            TUTOR_LOCATION_NAMES=("Route 212", "Survival Area"),
            parse_tutor_move_table=Mock(return_value=[move_1, move_2]),
            parse_tutor_compatibility_table=Mock(return_value=[compat_1]),
        )
        adapter = SimpleNamespace(
            formats=SimpleNamespace(tutors="overlay-table"), tutors=engine
        )
        overlay = SimpleNamespace(id=5, file_id=42)
        platform = SimpleNamespace(
            read_overlay=Mock(return_value=(overlay, b"\x00" * 8))
        )

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(f"{MODULE}.get_platform", return_value=platform),
            patch(f"{MODULE}._extract_special_tutors", return_value=([], [])),
        ):
            dataset = extract_tutor_dataset(result)

        engine.parse_tutor_move_table.assert_called_once_with(
            b"\x00" * 4, tutor_count=2
        )
        engine.parse_tutor_compatibility_table.assert_called_once_with(
            b"\x00" * 4,
            tutor_count=2,
            base_species_count=3,
            form_member_start=10,
            form_count=1,
        )
        self.assertEqual(dataset["dataset"], "move_tutors")
        self.assertEqual(
            dataset["records"],
            [
                {"tutor_id": 1, "kind": "shard"},
                {"tutor_id": 2, "kind": "shard"},
            ],
        )
        self.assertEqual(dataset["compatibility_record_count"], 1)
        self.assertEqual(dataset["special_record_count"], 0)
        self.assertEqual(dataset["special_compatibility_record_count"], 0)
        self.assertEqual(
            dataset["location_names"], ["Route 212", "Survival Area"]
        )
        self.assertEqual(
            dataset["compatibility"], [{"personal_member": 1}]
        )
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "deadbeef",
                "overlay_id": 5,
                "file_id": 42,
                "move_offset": 0,
                "compatibility_offset": 4,
            },
        )

    def test_overlay_table_rejects_an_unknown_tutor_location(self) -> None:
        profile = replace(
            _profile(),
            parameters={
                "tutor_overlay_id": 5,
                "tutor_move_offset": 0,
                "tutor_count": 1,
                "tutor_compatibility_offset": 2,
            },
        )
        result = _result(profile)

        move_1 = SimpleNamespace(location_id=99, to_dict=Mock(return_value={}))
        engine = SimpleNamespace(
            TUTOR_RECORD_SIZE=2,
            TUTOR_COMPATIBILITY_RECORD_SIZE=1,
            FORM_MEMBERS=frozenset({10}),
            BASE_SPECIES_COUNT=3,
            TUTOR_LOCATION_NAMES=("Route 212",),
            parse_tutor_move_table=Mock(return_value=[move_1]),
            parse_tutor_compatibility_table=Mock(),
        )
        adapter = SimpleNamespace(
            formats=SimpleNamespace(tutors="overlay-table"), tutors=engine
        )
        overlay = SimpleNamespace(id=5, file_id=42)
        platform = SimpleNamespace(
            read_overlay=Mock(return_value=(overlay, b"\x00" * 8))
        )

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(f"{MODULE}.get_platform", return_value=platform),
            self.assertRaisesRegex(InvalidRomError, "unknown location ID"),
        ):
            extract_tutor_dataset(result)


class SliceOverlayTests(unittest.TestCase):
    def test_slices_a_valid_range(self) -> None:
        self.assertEqual(_slice_overlay(b"0123456789", 2, 3, "move"), b"234")

    def test_rejects_a_negative_offset(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "outside its overlay"):
            _slice_overlay(b"0123456789", -1, 3, "move")

    def test_rejects_a_range_extending_past_the_data(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "outside its overlay"):
            _slice_overlay(b"0123456789", 8, 5, "move")


class OverlayArchiveTutorTests(unittest.TestCase):
    def test_requires_its_profile_metadata(self) -> None:
        profile = replace(_profile(), parameters={}, layout={})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "missing HGSS tutor metadata"):
            _extract_overlay_archive_tutors(result)

    def test_success_path(self) -> None:
        profile = replace(
            _profile(),
            parameters={"tutor_overlay_id": 9, "tutor_move_offset": 0},
            layout={"tutor_compatibility": "tutor_compat.narc"},
        )
        result = _result(profile)

        move_1 = Mock(to_dict=Mock(return_value={"tutor_id": 1}))
        compat_1 = Mock(to_dict=Mock(return_value={"personal_member": 1}))
        engine = SimpleNamespace(
            TUTOR_COUNT=1,
            TUTOR_RECORD_SIZE=4,
            FORM_MEMBERS=frozenset({10}),
            BASE_SPECIES_COUNT=3,
            TUTOR_LOCATION_NAMES=("Route 1",),
            parse_tutor_move_table=Mock(return_value=[move_1]),
            parse_tutor_compatibility_table=Mock(return_value=[compat_1]),
        )
        adapter = SimpleNamespace(tutors=engine)
        overlay = SimpleNamespace(id=9, file_id=99)
        filesystem = Mock()
        filesystem.read.return_value = b"compat-bytes"
        platform = SimpleNamespace(
            read_overlay_decompressed=Mock(return_value=(overlay, b"\x00" * 4)),
            filesystem_from_image=Mock(return_value=filesystem),
        )

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(f"{MODULE}.get_platform", return_value=platform),
        ):
            dataset = _extract_overlay_archive_tutors(result)

        engine.parse_tutor_move_table.assert_called_once_with(b"\x00" * 4)
        engine.parse_tutor_compatibility_table.assert_called_once_with(
            b"compat-bytes",
            base_species_count=3,
            form_member_start=10,
            form_count=1,
        )
        self.assertEqual(
            dataset["records"], [{"tutor_id": 1, "kind": "battle-points"}]
        )
        self.assertEqual(dataset["compatibility_record_count"], 1)
        self.assertEqual(dataset["special_record_count"], 0)
        self.assertEqual(dataset["compatibility"], [{"personal_member": 1}])
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "deadbeef",
                "overlay_id": 9,
                "file_id": 99,
                "move_offset": 0,
                "compatibility_archive": "tutor_compat.narc",
            },
        )


class PersonalArchiveTutorTests(unittest.TestCase):
    def test_requires_its_profile_metadata(self) -> None:
        profile = replace(_profile(), parameters={}, layout={})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "missing B2W2 tutor metadata"):
            _extract_personal_archive_tutors(result)

    def test_success_path(self) -> None:
        profile = replace(
            _profile(),
            parameters={"tutor_overlay_id": 3, "tutor_move_offset": 0},
            layout={"personal": "personal.narc"},
        )
        result = _result(profile)

        move_1 = Mock(to_dict=Mock(return_value={"tutor_id": 1}))
        compat_records = {
            1: Mock(to_dict=Mock(return_value={"personal_member": 1})),
            2: Mock(to_dict=Mock(return_value={"personal_member": 2})),
            10: Mock(to_dict=Mock(return_value={"personal_member": 10})),
        }
        engine = SimpleNamespace(
            TUTOR_COUNT=1,
            TUTOR_RECORD_SIZE=4,
            FORM_MEMBERS=frozenset({10}),
            BASE_SPECIES_COUNT=2,
            TUTOR_LOCATION_NAMES=("Route 1",),
            TUTOR_COMPATIBILITY_OFFSET=100,
            parse_tutor_move_table=Mock(return_value=[move_1]),
            parse_tutor_compatibility_record=Mock(
                side_effect=lambda data, personal_member: compat_records[
                    personal_member
                ]
            ),
        )
        adapter = SimpleNamespace(tutors=engine)
        overlay = SimpleNamespace(id=3, file_id=30)
        personal_archive = Mock()
        personal_archive.read.side_effect = lambda member: f"raw-{member}".encode()
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = personal_archive
        filesystem = Mock()
        filesystem.read.return_value = b"personal-bytes"
        platform = SimpleNamespace(
            read_overlay_decompressed=Mock(return_value=(overlay, b"\x00" * 4)),
            filesystem_from_image=Mock(return_value=filesystem),
            archive_cls=archive_cls,
        )

        with (
            patch(f"{MODULE}.get_engine", return_value=adapter),
            patch(f"{MODULE}.get_platform", return_value=platform),
        ):
            dataset = _extract_personal_archive_tutors(result)

        self.assertEqual(
            dataset["records"], [{"tutor_id": 1, "kind": "shard"}]
        )
        self.assertEqual(dataset["compatibility_record_count"], 3)
        self.assertEqual(
            dataset["compatibility"],
            [
                {"personal_member": 1},
                {"personal_member": 2},
                {"personal_member": 10},
            ],
        )
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "deadbeef",
                "overlay_id": 3,
                "file_id": 30,
                "move_offset": 0,
                "compatibility_archive": "personal.narc",
                "compatibility_offset": 100,
            },
        )


class SpecialTutorTests(unittest.TestCase):
    def test_returns_nothing_when_no_definitions_are_configured(self) -> None:
        profile = replace(_profile(), parameters={"special_tutors": []})
        result = _result(profile)

        records, compatibility = _extract_special_tutors(
            Mock(), Mock(), result, start_tutor_id=1
        )

        self.assertEqual(records, [])
        self.assertEqual(compatibility, [])

    def test_requires_definitions_to_be_a_list(self) -> None:
        profile = replace(_profile(), parameters={"special_tutors": "bad"})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "must be a list"):
            _extract_special_tutors(Mock(), Mock(), result, start_tutor_id=1)

    def test_requires_its_profile_metadata(self) -> None:
        profile = replace(
            _profile(),
            parameters={"special_tutors": [{}]},
            layout={},
        )
        result = _result(profile)

        with self.assertRaisesRegex(
            ProfileError, "missing special tutor metadata"
        ):
            _extract_special_tutors(Mock(), Mock(), result, start_tutor_id=1)

    def test_rejects_an_incomplete_definition(self) -> None:
        profile, platform, engine = _special_tutor_fixture(
            [{"script_member": 0}]
        )
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=()),
            self.assertRaisesRegex(ProfileError, "definition is incomplete"),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_rejects_an_unknown_script_member(self) -> None:
        definition = _species_definition(script_member=99)
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
            self.assertRaisesRegex(ProfileError, "unknown script member"),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_rejects_an_unknown_map_header(self) -> None:
        definition = _species_definition(map_header_id=99)
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
            self.assertRaisesRegex(ProfileError, "unknown map header"),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_rejects_a_map_header_mismatched_with_the_script(self) -> None:
        definition = _species_definition()
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)
        mismatched_header = _header(script_file_id=999)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(
                f"{MODULE}.parse_map_header_table",
                return_value=(mismatched_header,),
            ),
            self.assertRaisesRegex(
                InvalidRomError, "does not reference script member"
            ),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_rejects_a_missing_location_name(self) -> None:
        definition = _species_definition()
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)
        header = _header(location_name_id=99)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(header,)),
            self.assertRaisesRegex(InvalidRomError, "missing location name"),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_rejects_an_unknown_eligibility_kind(self) -> None:
        definition = _species_definition(eligibility_kind="mystery")
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
            self.assertRaisesRegex(ProfileError, "eligibility kind is unknown"),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_species_based_definition_requires_its_fields(self) -> None:
        definition = _species_definition()
        del definition["comparison_offset"]
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
            self.assertRaisesRegex(
                ProfileError, "Species-based special tutor definition"
            ),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_type_based_definition_requires_its_fields(self) -> None:
        definition = _type_definition()
        del definition["eligibility_value"]
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
            self.assertRaisesRegex(
                ProfileError, "Type-based special tutor definition"
            ),
        ):
            _extract_special_tutors(engine, platform, result, start_tutor_id=1)

    def test_species_based_success_path(self) -> None:
        definition = _species_definition()
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)
        engine.parse_special_tutor_species.return_value = {1, 2}
        tutor = Mock(to_dict=Mock(return_value={"tutor_id": 7}))
        engine.parse_special_tutor_move.return_value = tutor

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
        ):
            records, compatibility = _extract_special_tutors(
                engine, platform, result, start_tutor_id=7
            )

        engine.parse_special_tutor_species.assert_called_once_with(
            b"script-data", comparison_offset=20, species_count=2
        )
        engine.parse_special_tutor_move.assert_called_once_with(
            b"script-data",
            tutor_id=7,
            script_member=0,
            command_offset=10,
            map_header_id=0,
            location_name="Route 212",
            eligibility_kind="species",
            eligibility_value={1, 2},
            minimum_friendship=255,
        )
        self.assertEqual(records, [{"tutor_id": 7, "kind": "special"}])
        self.assertEqual(
            compatibility,
            [
                {"personal_member": 1, "tutor_ids": [7]},
                {"personal_member": 2, "tutor_ids": [7]},
            ],
        )

    def test_type_based_success_path(self) -> None:
        definition = _type_definition(eligibility_value=9)
        profile, platform, engine = _special_tutor_fixture([definition])
        result = _result(profile)
        tutor = Mock(to_dict=Mock(return_value={"tutor_id": 7}))
        engine.parse_special_tutor_move.return_value = tutor

        def type_ids(member: int) -> tuple[int, ...]:
            return {1: (9,), 2: (3,), 10: (9, 4)}[member]

        engine.parse_personal_record.side_effect = lambda data, species_id, archive_path: (
            SimpleNamespace(type_ids=type_ids(species_id))
        )

        with (
            patch(f"{MODULE}.read_code_binary", return_value=b"arm9"),
            patch(f"{MODULE}.parse_map_header_table", return_value=(_header(),)),
        ):
            records, compatibility = _extract_special_tutors(
                engine, platform, result, start_tutor_id=7
            )

        engine.parse_special_tutor_move.assert_called_once_with(
            b"script-data",
            tutor_id=7,
            script_member=0,
            command_offset=10,
            map_header_id=0,
            location_name="Route 212",
            eligibility_kind="type",
            eligibility_value=9,
            minimum_friendship=255,
        )
        self.assertEqual(records, [{"tutor_id": 7, "kind": "special"}])
        self.assertEqual(
            compatibility,
            [
                {"personal_member": 1, "tutor_ids": [7]},
                {"personal_member": 10, "tutor_ids": [7]},
            ],
        )


def _species_definition(**overrides: object) -> dict[str, object]:
    definition = {
        "script_member": 0,
        "command_offset": 10,
        "map_header_id": 0,
        "eligibility_kind": "species",
        "comparison_offset": 20,
        "species_count": 2,
    }
    definition.update(overrides)
    return definition


def _type_definition(**overrides: object) -> dict[str, object]:
    definition = {
        "script_member": 0,
        "command_offset": 10,
        "map_header_id": 0,
        "eligibility_kind": "type",
        "eligibility_value": 7,
    }
    definition.update(overrides)
    return definition


def _header(
    *, script_file_id: int = 0, location_name_id: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(
        script_file_id=script_file_id, location_name_id=location_name_id
    )


def _special_tutor_fixture(
    definitions: list[dict[str, object]],
) -> tuple[GameProfile, SimpleNamespace, SimpleNamespace]:
    profile = replace(
        _profile(),
        layout={
            "scripts": "scripts.narc",
            "personal": "personal.narc",
            "map_names": "map_names.narc",
            "messages": "messages.narc",
        },
        parameters={
            "special_tutors": definitions,
            "location_names_member": 3,
            "map_header_offset": 0,
            "map_header_count": 1,
        },
    )

    scripts_archive = Mock()
    scripts_archive.members = [SimpleNamespace()]
    scripts_archive.read.return_value = b"script-data"
    personal_archive = Mock()
    personal_archive.read.side_effect = lambda member: f"raw-{member}".encode()
    messages_archive = Mock()
    messages_archive.read.return_value = b"raw-location-names"

    archive_cls = Mock()

    def from_bytes(data: bytes, allow_truncated: bool = False) -> Mock:
        return {
            b"scripts-bytes": scripts_archive,
            b"personal-bytes": personal_archive,
            b"messages-bytes": messages_archive,
        }[data]

    archive_cls.from_bytes.side_effect = from_bytes

    filesystem = Mock()

    def read(path: str) -> bytes:
        return {
            "scripts.narc": b"scripts-bytes",
            "personal.narc": b"personal-bytes",
            "messages.narc": b"messages-bytes",
        }[path]

    filesystem.read.side_effect = read
    platform = SimpleNamespace(
        filesystem_from_image=Mock(return_value=filesystem), archive_cls=archive_cls
    )

    engine = SimpleNamespace(
        MAX_FRIENDSHIP=255,
        BASE_SPECIES_COUNT=2,
        FORM_MEMBERS=frozenset({10}),
        parse_english_message_archive=Mock(return_value=("Route 212",)),
        parse_personal_record=Mock(
            side_effect=lambda data, species_id, archive_path: SimpleNamespace(
                type_ids=()
            )
        ),
        parse_special_tutor_species=Mock(),
        parse_special_tutor_move=Mock(),
    )
    return profile, platform, engine


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
        layout={},
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
