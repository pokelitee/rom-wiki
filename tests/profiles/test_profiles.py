from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.platforms.nds.reader import NintendoDSImage, RomHashes
from romwiki.profiles.loader import ProfileRepository
from romwiki.util.errors import ProfileError
from tests.conftest import make_header


class ProfileRepositoryTests(unittest.TestCase):
    def test_loads_clean_platinum_baseline_profile(self) -> None:
        profiles = ProfileRepository.load(Path("profiles")).profiles

        profile = next(value for value in profiles if value.id == "platinum-us")

        self.assertEqual(profile.platform, "nintendo-ds")
        self.assertEqual(profile.engine, "gen4_dppt")
        self.assertEqual(profile.base_game, "platinum")
        self.assertEqual(profile.rom_versions, (0,))
        self.assertEqual(profile.parameters["egg_gifts"][0]["command_offset"], 0xE59)

    def test_loads_black_and_white_baseline_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        black = profiles["black-us"]
        white = profiles["white-us"]

        self.assertEqual(black.platform, "nintendo-ds")
        self.assertEqual(black.engine, "gen5_bw")
        self.assertEqual(black.base_game, "black")
        self.assertEqual(black.game_codes, ("IRBO",))
        self.assertEqual(black.rom_versions, (0,))
        self.assertEqual(black.layout["personal"], "a/0/1/6")
        self.assertEqual(black.layout["messages"], "a/0/0/2")
        self.assertEqual(black.layout["item_data"], "a/0/2/4")
        self.assertEqual(black.parameters["pokemon_names_member"], 70)
        self.assertEqual(black.parameters["ability_names_member"], 182)
        self.assertEqual(black.parameters["move_names_member"], 203)
        self.assertEqual(black.parameters["item_names_member"], 54)
        self.assertEqual(black.sprite_version, "black-white")

        self.assertEqual(white.engine, "gen5_bw")
        self.assertEqual(white.base_game, "white")
        self.assertEqual(white.game_codes, ("IRAO",))
        self.assertEqual(white.layout["messages"], "a/0/0/2")
        self.assertEqual(white.parameters["pokemon_names_member"], 70)
        self.assertEqual(white.layout["personal"], "a/0/1/6")
        self.assertEqual(white.layout["item_data"], "a/0/2/4")

    def test_matches_a_known_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "test.toml"
            profile_path.write_text(
                """
[profile]
id = "test"
name = "Test Profile"
platform = "nintendo-ds"
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
platform = "nintendo-ds"
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
platform = "nintendo-ds"
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

    def test_rejects_profile_missing_platform(self) -> None:
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
[[hashes]]
algorithm = "sha256"
value = "abcd"
variant = "test"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProfileError, "Invalid profile"):
                ProfileRepository.load(Path(directory))


if __name__ == "__main__":
    unittest.main()
