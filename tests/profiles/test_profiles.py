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
        self.assertEqual(black.layout["moves"], "a/0/2/1")
        self.assertEqual(black.layout["learnsets"], "a/0/1/8")
        self.assertEqual(black.layout["evolutions"], "a/0/1/9")
        self.assertEqual(black.layout["egg_moves"], "a/1/2/3")
        self.assertEqual(black.layout["encounters"], "a/1/2/6")
        self.assertEqual(black.layout["trainer_data"], "a/0/9/2")
        self.assertEqual(black.layout["trainer_parties"], "a/0/9/3")
        self.assertEqual(black.layout["map_headers"], "a/0/1/2")
        self.assertEqual(black.layout["npc_trades"], "a/1/6/5")
        self.assertEqual(black.layout["scripts"], "a/0/5/7")
        self.assertEqual(black.parameters["pokemon_names_member"], 70)
        self.assertEqual(black.parameters["ability_names_member"], 182)
        self.assertEqual(black.parameters["move_names_member"], 203)
        self.assertEqual(black.parameters["item_names_member"], 54)
        self.assertEqual(black.parameters["machine_move_prefix"], "87038803")
        self.assertEqual(black.parameters["trainer_names_member"], 190)
        self.assertEqual(black.parameters["trainer_classes_member"], 191)
        self.assertEqual(black.parameters["map_names_member"], 89)
        self.assertEqual(black.parameters["npc_trade_names_member"], 35)
        self.assertEqual(
            black.parameters["npc_trades_unused"], [1, 3, 7, 8, 9, 10, 11, 12]
        )
        self.assertEqual(black.parameters["static_pokemon_egg_indices"], [5])
        self.assertEqual(len(black.parameters["static_pokemon"]), 31)
        self.assertEqual(
            black.parameters["static_pokemon"][0], {"species": [304, 0x121], "level": [304, 0x29D]}
        )
        self.assertEqual(black.sprite_version, "black-white")

        self.assertEqual(white.engine, "gen5_bw")
        self.assertEqual(white.base_game, "white")
        self.assertEqual(white.game_codes, ("IRAO",))
        self.assertEqual(white.layout["messages"], "a/0/0/2")
        self.assertEqual(white.parameters["pokemon_names_member"], 70)
        self.assertEqual(white.layout["personal"], "a/0/1/6")
        self.assertEqual(white.layout["item_data"], "a/0/2/4")
        self.assertEqual(white.layout["trainer_data"], "a/0/9/2")
        self.assertEqual(white.layout["map_headers"], "a/0/1/2")
        self.assertEqual(white.layout["npc_trades"], "a/1/6/5")
        self.assertEqual(white.layout["scripts"], "a/0/5/7")
        self.assertEqual(
            white.parameters["npc_trades_unused"], [0, 2, 7, 8, 9, 10, 11, 12]
        )
        self.assertEqual(white.parameters["static_pokemon"], black.parameters["static_pokemon"])

    def test_loads_blaze_black_and_volt_white_profiles(self) -> None:
        profiles = {
            value.id: value
            for value in ProfileRepository.load(Path("profiles")).profiles
        }

        blaze = profiles["blaze-black"]
        volt = profiles["volt-white"]

        self.assertEqual(blaze.engine, "gen5_bw")
        self.assertEqual(blaze.base_game, "black")
        self.assertEqual(blaze.game_codes, ("IRBO",))
        self.assertEqual(blaze.hashes[0].variant, "full-v3.1")
        self.assertEqual(
            blaze.hashes[0].value,
            "340c1416b2b107a59c9305c43747761804edce8e876c364abee1f0189bd768ac",
        )
        self.assertEqual(volt.engine, "gen5_bw")
        self.assertEqual(volt.base_game, "white")
        self.assertEqual(volt.game_codes, ("IRAO",))
        self.assertEqual(volt.hashes[0].variant, "full-v3.1")
        self.assertEqual(
            volt.hashes[0].value,
            "232043c9e3f979fff9e1fd67b78d759928e7849b4c2516477b43538fbf7bf851",
        )

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
