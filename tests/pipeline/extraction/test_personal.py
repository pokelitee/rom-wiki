from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.engines.registry import (
    EngineAdapter,
    EngineFormats,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.personal import extract_personal_dataset
from romwiki.platforms.nds import NarcMember
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.versions import POKEMON_PERSONAL_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError

_PLATFORM_ID = "fake-personal-platform"
_FLAT_PLATFORM_ID = "fake-flat-personal-platform"
_ENGINE_ID = "fake_personal_engine"


class _FakeArchive:
    """Members are one-byte records, followed by `trailing` larger members."""

    def __init__(self, member_count: int, *, trailing: int = 0) -> None:
        self.members = tuple(
            NarcMember(index=index, start=0, end=0)
            for index in range(member_count + trailing)
        )
        self._record_count = member_count

    def read(self, index: int) -> bytes:
        if index >= self._record_count:
            return bytes(16)
        return bytes([index])


def _register_fake_platform(archive: _FakeArchive) -> None:
    archive_cls = Mock()
    archive_cls.from_bytes.return_value = archive
    register_platform(
        _PLATFORM_ID,
        PlatformAdapter(
            inspect=lambda path: None,
            filesystem_from_image=lambda image: Mock(read=Mock(return_value=b"raw")),
            matches_header=lambda image, codes, versions: True,
            archive_cls=archive_cls,
        ),
    )


def _register_fake_flat_platform(rom: bytes) -> None:
    register_platform(
        _FLAT_PLATFORM_ID,
        PlatformAdapter(
            inspect=lambda path: None,
            filesystem_from_image=lambda image: None,
            matches_header=lambda image, codes, versions: True,
            read_bytes=lambda image, offset, size: rom[offset : offset + size],
        ),
    )


def _decode_ascii_table(data: bytes, *, stride: int, count: int) -> list[str]:
    return [
        data[index * stride : (index + 1) * stride].split(b"\xff")[0].decode()
        for index in range(count)
    ]


def _register_fake_engine(personal: SimpleNamespace) -> None:
    fields = dict.fromkeys(EngineAdapter.__dataclass_fields__, SimpleNamespace())
    fields["personal"] = personal
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
    defaults = {
        "id": "test-personal",
        "name": "Test Personal",
        "platform": _PLATFORM_ID,
        "engine": _ENGINE_ID,
        "base_game": "test",
        "game_codes": (),
        "rom_versions": (),
        "hashes": (KnownHash(algorithm="sha256", value="abc123", variant="retail"),),
        "layout": {"personal": "personal.narc"},
        "parameters": {},
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


def _parse_record(data: bytes, *, species_id: int, archive_path: str, **kwargs: object):
    return SimpleNamespace(to_dict=lambda: {"species_id": species_id, **kwargs})


class ExtractPersonalDatasetTests(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_platform(_PLATFORM_ID)
        unregister_platform(_FLAT_PLATFORM_ID)
        unregister_engine(_ENGINE_ID)

    def test_raises_without_a_matched_profile(self) -> None:
        with self.assertRaisesRegex(
            ProfileError, "known game profile is required for personal-data"
        ):
            extract_personal_dataset(_result(None))

    def test_raises_when_profile_has_no_personal_archive(self) -> None:
        profile = _profile(layout={})
        _register_fake_platform(_FakeArchive(1))
        _register_fake_engine(
            SimpleNamespace(parse_personal_record=_parse_record, PERSONAL_RECORD_SIZE=1)
        )

        with self.assertRaisesRegex(ProfileError, "does not define a personal archive"):
            extract_personal_dataset(_result(profile))

    def test_extracts_every_record_before_a_trailing_non_record_member(self) -> None:
        profile = _profile()
        _register_fake_platform(_FakeArchive(3, trailing=1))
        _register_fake_engine(
            SimpleNamespace(parse_personal_record=_parse_record, PERSONAL_RECORD_SIZE=1)
        )

        with (
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_names",
                return_value={"type_names": ["Normal", "Fire"]},
            ),
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_descriptions",
                return_value={"ability_descriptions": ["desc"]},
            ) as descriptions,
        ):
            dataset = extract_personal_dataset(_result(profile))

        self.assertEqual(dataset["schema_version"], POKEMON_PERSONAL_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "pokemon_personal")
        self.assertEqual(dataset["record_count"], 3)
        self.assertEqual(
            dataset["records"],
            [{"species_id": 0}, {"species_id": 1}, {"species_id": 2}],
        )
        self.assertEqual(
            dataset["source"], {"rom_sha256": "abc123", "archive": "personal.narc"}
        )
        self.assertEqual(dataset["type_names"], ["Normal", "Fire"])
        self.assertEqual(dataset["ability_descriptions"], ["desc"])
        self.assertEqual(
            descriptions.call_args.kwargs["fields"],
            {"ability_descriptions", "pokemon_descriptions"},
        )

    def test_passes_the_repair_flag_when_the_profile_requests_it(self) -> None:
        profile = _profile(
            parameters={"repair_invalid_secondary_egg_group": True},
        )
        _register_fake_platform(_FakeArchive(1))
        _register_fake_engine(
            SimpleNamespace(parse_personal_record=_parse_record, PERSONAL_RECORD_SIZE=1)
        )

        with (
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_names",
                return_value={},
            ),
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_descriptions",
                return_value={},
            ),
        ):
            dataset = extract_personal_dataset(_result(profile))

        self.assertEqual(
            dataset["records"],
            [{"species_id": 0, "repair_invalid_secondary_egg_group": True}],
        )

    def test_omits_the_repair_flag_by_default(self) -> None:
        profile = _profile()
        _register_fake_platform(_FakeArchive(1))
        _register_fake_engine(
            SimpleNamespace(parse_personal_record=_parse_record, PERSONAL_RECORD_SIZE=1)
        )

        with (
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_names",
                return_value={},
            ),
            patch(
                "romwiki.pipeline.extraction.personal.extract_reference_descriptions",
                return_value={},
            ),
        ):
            dataset = extract_personal_dataset(_result(profile))

        self.assertEqual(dataset["records"], [{"species_id": 0}])

    def test_reads_one_flat_species_name_per_record(self) -> None:
        # Two one-byte records at 0x00, species names (stride 2) at 0x10 and
        # ability names (stride 3) at 0x20.
        rom = bytearray(0x30)
        rom[0x10:0x14] = b"ABZ\xff"
        rom[0x20:0x26] = b"XY\xffQR\xff"
        profile = _profile(
            platform=_FLAT_PLATFORM_ID,
            layout={},
            parameters={
                "personal_offset": 0x00,
                "personal_count": 2,
                "pokemon_name_offset": 0x10,
                "pokemon_name_stride": 2,
                "ability_name_offset": 0x20,
                "ability_name_stride": 3,
            },
        )
        _register_fake_flat_platform(bytes(rom))
        _register_fake_engine(
            SimpleNamespace(
                parse_personal_record=_parse_record,
                PERSONAL_RECORD_SIZE=1,
                ABILITY_NAME_COUNT=2,
                decode_gen3_name_table=_decode_ascii_table,
            )
        )

        dataset = extract_personal_dataset(_result(profile))

        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["pokemon_names"], ["AB", "Z"])
        self.assertEqual(dataset["ability_names"], ["XY", "QR"])
        self.assertEqual(
            dataset["name_sources"],
            {
                "ability_names": {"archive": "offset:0x20", "member": 0},
                "pokemon_names": {"archive": "offset:0x10", "member": 0},
            },
        )

    def test_flat_profiles_without_name_offsets_get_no_names(self) -> None:
        profile = _profile(
            platform=_FLAT_PLATFORM_ID,
            layout={},
            parameters={"personal_offset": 0, "personal_count": 1},
        )
        _register_fake_flat_platform(bytes(4))
        _register_fake_engine(
            SimpleNamespace(
                parse_personal_record=_parse_record,
                PERSONAL_RECORD_SIZE=1,
                ABILITY_NAME_COUNT=2,
            )
        )

        dataset = extract_personal_dataset(_result(profile))

        self.assertNotIn("pokemon_names", dataset)
        self.assertNotIn("name_sources", dataset)


if __name__ == "__main__":
    unittest.main()
