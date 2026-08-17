from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from romwiki.pipeline.extraction.identify import inspect_rom
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import GameProfile, KnownHash
from romwiki.util.errors import InvalidRomError, ProfileError

_PLATFORM_ID = "fake-identify-platform"
_MAGIC = b"FAKEROM"


@dataclass(frozen=True, slots=True)
class _FakeHashes:
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class _FakeImage:
    hashes: _FakeHashes

    def to_dict(self) -> dict[str, Any]:
        return {"hashes": self.hashes.to_dict()}


class _FakeArchive:
    @classmethod
    def from_bytes(cls, data: bytes, **_kwargs: object) -> _FakeArchive:
        return cls()


def _fake_inspect(rom_path: Path) -> _FakeImage:
    data = rom_path.read_bytes()
    if not data.startswith(_MAGIC):
        raise InvalidRomError(f"Not a recognized fake ROM image: {rom_path.name}")
    digest = hashlib.sha256(data).hexdigest()
    return _FakeImage(hashes=_FakeHashes(sha256=digest))


def _profile(digest: str, *, profile_id: str = "test-game") -> GameProfile:
    return GameProfile(
        id=profile_id,
        name="Test Game",
        platform=_PLATFORM_ID,
        engine="gen4_dppt",
        base_game="test",
        game_codes=(),
        rom_versions=(),
        hashes=(KnownHash(algorithm="sha256", value=digest, variant="retail"),),
    )


class InspectRomTests(unittest.TestCase):
    def setUp(self) -> None:
        register_platform(
            _PLATFORM_ID,
            PlatformAdapter(
                inspect=_fake_inspect,
                filesystem_from_image=lambda image: image,
                matches_header=lambda image, game_codes, rom_versions: True,
                archive_cls=_FakeArchive,
            ),
        )
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.addCleanup(unregister_platform, _PLATFORM_ID)

    def _write_rom(self, name: str, content: bytes) -> Path:
        path = Path(self.tmpdir.name) / name
        path.write_bytes(content)
        return path

    def test_matches_a_known_profile_by_hash(self) -> None:
        content = _MAGIC + b"\x00" * 32
        rom_path = self._write_rom("known.rom", content)
        digest = hashlib.sha256(content).hexdigest()
        repository = ProfileRepository((_profile(digest),))

        result = inspect_rom(rom_path, Path("unused"), profiles=repository)

        self.assertIsNotNone(result.match)
        self.assertEqual(result.match.profile.id, "test-game")
        self.assertEqual(result.match.known_hash.value, digest)
        self.assertEqual(result.match.known_hash.algorithm, "sha256")

    def test_returns_no_match_for_an_unrecognized_hash(self) -> None:
        content = _MAGIC + b"\x01" * 32
        rom_path = self._write_rom("unknown.rom", content)
        repository = ProfileRepository((_profile("0" * 64),))

        result = inspect_rom(rom_path, Path("unused"), profiles=repository)

        self.assertIsNone(result.match)
        self.assertIsNotNone(result.image)

    def test_raises_when_no_platform_accepts_the_image(self) -> None:
        rom_path = self._write_rom("bad.rom", b"NOTFAKE")
        repository = ProfileRepository((_profile("0" * 64),))

        with self.assertRaisesRegex(
            InvalidRomError, "No registered platform accepts"
        ):
            inspect_rom(rom_path, Path("unused"), profiles=repository)

    def test_raises_for_a_missing_rom_file(self) -> None:
        rom_path = Path(self.tmpdir.name) / "missing.rom"
        repository = ProfileRepository((_profile("0" * 64),))

        with self.assertRaises(FileNotFoundError):
            inspect_rom(rom_path, Path("unused"), profiles=repository)

    def test_to_dict_includes_matched_profile_metadata(self) -> None:
        content = _MAGIC + b"\x02" * 32
        rom_path = self._write_rom("known.rom", content)
        digest = hashlib.sha256(content).hexdigest()
        repository = ProfileRepository((_profile(digest),))

        result = inspect_rom(rom_path, Path("unused"), profiles=repository)
        data = result.to_dict()

        self.assertEqual(data["profile"]["id"], "test-game")
        self.assertEqual(data["profile"]["engine"], "gen4_dppt")
        self.assertEqual(data["profile"]["matched_by"], "sha256")

    def test_to_dict_reports_no_profile_when_unmatched(self) -> None:
        content = _MAGIC + b"\x03" * 32
        rom_path = self._write_rom("unknown.rom", content)
        repository = ProfileRepository((_profile("0" * 64),))

        result = inspect_rom(rom_path, Path("unused"), profiles=repository)
        data = result.to_dict()

        self.assertIsNone(data["profile"])

    def test_raises_when_the_image_matches_more_than_one_profile(self) -> None:
        content = _MAGIC + b"\x04" * 32
        rom_path = self._write_rom("known.rom", content)
        digest = hashlib.sha256(content).hexdigest()
        repository = ProfileRepository(
            (
                _profile(digest, profile_id="game-a"),
                _profile(digest, profile_id="game-b"),
            )
        )

        with self.assertRaisesRegex(ProfileError, "more than one profile"):
            inspect_rom(rom_path, Path("unused"), profiles=repository)

    def test_loads_profiles_from_a_directory_when_none_are_supplied(self) -> None:
        rom_path = self._write_rom("known.rom", _MAGIC + b"\x05" * 32)

        with self.assertRaises(ProfileError):
            inspect_rom(rom_path, Path(self.tmpdir.name) / "no-such-profiles-dir")


if __name__ == "__main__":
    unittest.main()
