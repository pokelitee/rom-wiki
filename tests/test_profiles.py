from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.errors import ProfileError
from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.platforms.nds.reader import NintendoDSImage, RomHashes
from romwiki.profiles.loader import ProfileRepository
from tests.test_nds_header import make_header


class ProfileRepositoryTests(unittest.TestCase):
    def test_matches_a_known_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
engine = "gen4_dppt"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[semantics.types]
9 = "fairy"
[semantics.moves]
66 = "play-rough"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )
            image = NintendoDSImage(
                path=Path("test.nds"),
                size=0x8000,
                header=NintendoDSHeader.from_bytes(make_header()),
                hashes=RomHashes(md5="", sha1="", sha256="abcd"),
            )

            match = ProfileRepository.load(Path(directory)).identify(image)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.profile.id, "test")
        self.assertEqual(match.profile.type_names, {9: "fairy"})
        self.assertEqual(match.profile.move_names, {66: "play-rough"})
        self.assertEqual(match.known_hash.variant, "test")

    def test_rejects_invalid_sprite_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
engine = "gen4_dppt"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[reference]
sprite_version = "Platinum Version"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid sprite version"):
                ProfileRepository.load(Path(directory))

    def test_rejects_invalid_type_semantic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
engine = "gen4_dppt"
base_game = "platinum"
[header]
game_codes = ["CPUE"]
rom_versions = [1]
[semantics.types]
9 = "Fairy Type"
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid type semantic"):
                ProfileRepository.load(Path(directory))


if __name__ == "__main__":
    unittest.main()
