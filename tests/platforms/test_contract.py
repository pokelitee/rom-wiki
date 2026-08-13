"""Proves extraction touches platforms only through `PlatformAdapter`: a fake
in-memory platform registered for these tests must serve a full personal-data
extraction, and ROM inspection must probe registered platforms rather than
assuming Nintendo DS.
"""

from __future__ import annotations

import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path

from romwiki.engines.registry import (
    EngineAdapter,
    EngineFormats,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.identify import InspectionResult, inspect_rom
from romwiki.pipeline.personal import extract_personal_dataset
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import DataSourceError

_FAKE_PLATFORM_ID = "fake-test-platform"
_FAKE_ENGINE_ID = "fake_platform_test_engine"


class _FakeImage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.hashes = types.SimpleNamespace(
            sha256="00" * 32,
            to_dict=lambda: {"sha256": "00" * 32},
        )

    def to_dict(self) -> dict:
        return {"source_name": "fake.bin", "hashes": self.hashes.to_dict()}


class _FakeArchive:
    def __init__(self, records: list[bytes]) -> None:
        self._records = records
        self.members = [
            types.SimpleNamespace(index=index) for index in range(len(records))
        ]

    @classmethod
    def from_bytes(cls, data: bytes, **_kwargs) -> _FakeArchive:
        return cls([data[index : index + 1] for index in range(len(data))])

    def read(self, index: int) -> bytes:
        return self._records[index]


class _FakeFileSystem:
    def __init__(self, files: dict[str, bytes]) -> None:
        self._files = files

    def read(self, path: str) -> bytes:
        return self._files[path]


def _fake_platform(files: dict[str, bytes]) -> PlatformAdapter:
    return PlatformAdapter(
        inspect=lambda path: _FakeImage(path),
        filesystem_from_image=lambda image: _FakeFileSystem(files),
        matches_header=lambda image, game_codes, rom_versions: True,
        archive_cls=_FakeArchive,
    )


class _FakeRecord:
    def __init__(self, species_id: int, value: int) -> None:
        self.species_id = species_id
        self.value = value

    def to_dict(self) -> dict:
        return {"species_id": self.species_id, "value": self.value}


def _parse_record(data: bytes, *, species_id: int, archive_path: str) -> _FakeRecord:
    return _FakeRecord(species_id, data[0])


def _fake_profile() -> GameProfile:
    return GameProfile(
        id="fake-game",
        name="Fake Game",
        platform=_FAKE_PLATFORM_ID,
        engine=_FAKE_ENGINE_ID,
        base_game="fake",
        game_codes=("FAKE",),
        rom_versions=(0,),
        hashes=(KnownHash(algorithm="sha256", value="00" * 32, variant="retail"),),
        layout={"personal": "personal.bin"},
    )


class PlatformContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_platform(_FAKE_PLATFORM_ID)
        unregister_engine(_FAKE_ENGINE_ID)

    def test_personal_extraction_uses_only_the_platform_adapter(self) -> None:
        register_platform(
            _FAKE_PLATFORM_ID, _fake_platform({"personal.bin": bytes([7, 9, 11])})
        )
        tables = types.SimpleNamespace(
            parse_personal_record=_parse_record, PERSONAL_RECORD_COUNT=3
        )
        engine_fields = dict.fromkeys(EngineAdapter.__dataclass_fields__, tables)
        engine_fields["generation"] = None
        engine_fields["dataset_kinds"] = frozenset({"pokemon"})
        engine_fields["required_dataset_kinds"] = frozenset({"pokemon"})
        engine_fields["formats"] = EngineFormats(
            encounters="conditional",
            locations="event-map",
            location_extraction="arm9-event-map",
            pickup="split-table",
            trainers="class-gender",
            tutors="none",
            fossils="none",
            static_encounters="none",
            egg_moves="none",
            item_archive="archive-index",
            machines="none",
        )
        register_engine(_FAKE_ENGINE_ID, EngineAdapter(**engine_fields), validate=False)
        profile = _fake_profile()
        result = InspectionResult(
            image=_FakeImage(),
            match=HashMatch(profile=profile, known_hash=profile.hashes[0]),
        )

        dataset = extract_personal_dataset(result)

        self.assertEqual(dataset["game"], "fake-game")
        self.assertEqual(dataset["engine"], _FAKE_ENGINE_ID)
        self.assertEqual(dataset["record_count"], 3)
        self.assertEqual(dataset["records"][1], {"species_id": 1, "value": 9})

    def test_inspection_probes_registered_platforms(self) -> None:
        register_platform(_FAKE_PLATFORM_ID, _fake_platform({}))
        with tempfile.TemporaryDirectory() as directory:
            rom_path = Path(directory) / "fake.bin"
            rom_path.write_bytes(b"not a nintendo ds image")

            result = inspect_rom(rom_path, Path("profiles"))

        # The Nintendo DS adapter rejects the file; the fake platform accepts
        # it, and no real profile matches the fake image.
        self.assertIsInstance(result.image, _FakeImage)
        self.assertIsNone(result.match)

    def test_registration_rejects_an_incomplete_platform_adapter(self) -> None:
        adapter = replace(_fake_platform({}), archive_cls=object)

        with self.assertRaisesRegex(DataSourceError, "archive_cls.from_bytes"):
            register_platform(_FAKE_PLATFORM_ID, adapter)


if __name__ == "__main__":
    unittest.main()
