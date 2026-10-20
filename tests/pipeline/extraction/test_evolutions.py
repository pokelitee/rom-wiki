from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from romwiki.engines.registry import (
    EngineAdapter,
    EngineFormats,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.extraction.evolutions import extract_evolution_dataset
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.nds import NarcMember
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.versions import POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError

_PLATFORM_ID = "fake-evolutions-platform"
_ENGINE_ID = "fake_evolutions_engine"


class _FakeArchive:
    def __init__(self, member_count: int) -> None:
        self.members = tuple(
            NarcMember(index=index, start=0, end=0) for index in range(member_count)
        )

    def read(self, index: int) -> bytes:
        return bytes([index])


def _register_fake_platform(
    evolutions_archive: _FakeArchive, messages_archive: Mock
) -> Mock:
    archive_cls = Mock()
    archive_cls.from_bytes.side_effect = [evolutions_archive, messages_archive]
    register_platform(
        _PLATFORM_ID,
        PlatformAdapter(
            inspect=lambda path: None,
            filesystem_from_image=lambda image: Mock(read=Mock(return_value=b"raw")),
            matches_header=lambda image, codes, versions: True,
            archive_cls=archive_cls,
        ),
    )
    return archive_cls


def _register_fake_engine(
    evolutions: SimpleNamespace, personal_record_count: int
) -> None:
    fields: dict[str, Any] = dict.fromkeys(
        EngineAdapter.__dataclass_fields__, SimpleNamespace()
    )
    fields["evolutions"] = evolutions
    # The species count comes from the personal archive, tested on its own.
    patch(
        "romwiki.pipeline.extraction.evolutions.personal_archive_count",
        return_value=personal_record_count,
    ).start()
    fields["generation"] = None
    fields["dataset_kinds"] = frozenset({"pokemon"})
    fields["required_dataset_kinds"] = frozenset({"pokemon"})
    fields["formats"] = EngineFormats(
        encounters="unsupported",
        locations="unsupported",
        location_extraction="unsupported",
        pickup="none",
        trainers="unsupported",
        tutors="none",
        fossils="none",
        static_encounters="none",
        egg_moves="none",
        item_archive="archive-index",
        machines="none",
    )
    register_engine(_ENGINE_ID, EngineAdapter(**fields), validate=False)


def _profile(**overrides: object) -> GameProfile:
    defaults: dict[str, Any] = {
        "id": "test-evolutions",
        "name": "Test Evolutions",
        "platform": _PLATFORM_ID,
        "engine": _ENGINE_ID,
        "base_game": "test",
        "game_codes": (),
        "rom_versions": (),
        "hashes": (KnownHash(algorithm="sha256", value="abc123", variant="retail"),),
        "layout": {"evolutions": "evolutions.narc", "messages": "messages.narc"},
        "parameters": {"item_names_member": 5},
    }
    defaults.update(overrides)
    return GameProfile(**defaults)


def _result(profile: GameProfile | None) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "abc123"
    match = None
    if profile is not None:
        match = HashMatch(profile=profile, known_hash=profile.hashes[0])
    return InspectionResult(image=image, match=match)


def _parse_evolution_record(data: bytes, *, species_id: int, archive_path: str):
    return SimpleNamespace(to_dict=lambda: {"species_id": species_id})


class ExtractEvolutionDatasetTests(unittest.TestCase):
    def tearDown(self) -> None:
        patch.stopall()
        unregister_platform(_PLATFORM_ID)
        unregister_engine(_ENGINE_ID)

    def test_raises_without_a_matched_profile(self) -> None:
        with self.assertRaisesRegex(
            ProfileError, "known game profile is required for evolution"
        ):
            extract_evolution_dataset(_result(None))

    def test_raises_when_item_name_metadata_is_missing(self) -> None:
        profile = _profile(parameters={})
        _register_fake_platform(_FakeArchive(1), Mock())
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(),
                parse_evolution_record=_parse_evolution_record,
            ),
            personal_record_count=1,
        )

        with self.assertRaisesRegex(
            ProfileError, "does not define evolution item-name data"
        ):
            extract_evolution_dataset(_result(profile))

    def test_extracts_records_bounded_to_the_personal_archive_count(self) -> None:
        profile = _profile()
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        _register_fake_platform(_FakeArchive(4), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(
                    return_value=("Fire Stone", "Water Stone")
                ),
                parse_evolution_record=_parse_evolution_record,
            ),
            personal_record_count=2,
        )

        dataset = extract_evolution_dataset(_result(profile))

        self.assertEqual(
            dataset["schema_version"], POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION
        )
        self.assertEqual(dataset["dataset"], "evolutions")
        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["records"], [{"species_id": 0}, {"species_id": 1}])
        self.assertEqual(dataset["item_names"], ["Fire Stone", "Water Stone"])
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "abc123",
                "archive": "evolutions.narc",
                "item_names": {"archive": "messages.narc", "member": 5},
            },
        )

    def test_passes_allow_truncated_flags_to_both_archives(self) -> None:
        profile = _profile(
            parameters={
                "item_names_member": 5,
                "evolutions_allow_truncated": True,
                "messages_allow_truncated": True,
            }
        )
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        archive_cls = _register_fake_platform(_FakeArchive(1), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(return_value=()),
                parse_evolution_record=_parse_evolution_record,
            ),
            personal_record_count=1,
        )

        extract_evolution_dataset(_result(profile))

        evolutions_call, messages_call = archive_cls.from_bytes.call_args_list
        self.assertTrue(evolutions_call.kwargs["allow_truncated"])
        self.assertTrue(messages_call.kwargs["allow_truncated"])


if __name__ == "__main__":
    unittest.main()
