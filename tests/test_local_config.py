from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.cli import _resolve_build_baseline, _resolve_input_rom, build_parser
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry


class LocalGameRegistryTests(unittest.TestCase):
    def test_resolves_relative_patched_and_base_paths_from_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roms = root / "roms"
            roms.mkdir()
            patched = roms / "patched.nds"
            base = roms / "base.nds"
            patched.touch()
            base.touch()
            config = root / "games.toml"
            config.write_text(
                """
version = 1
[games.test-game]
patched_rom = "roms/patched.nds"
base_rom = "roms/base.nds"
""".strip(),
                encoding="utf-8",
            )

            game = LocalGameRegistry.load(config).get("test-game")

            self.assertEqual(game.rom(), patched.resolve())
            self.assertEqual(game.rom(base=True), base.resolve())

    def test_does_not_require_base_rom_until_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            patched.touch()
            config = root / "games.toml"
            config.write_text(
                """
[games.test-game]
patched_rom = "patched.nds"
base_rom = "missing-base.nds"
""".strip(),
                encoding="utf-8",
            )

            game = LocalGameRegistry.load(config).get("test-game")

            self.assertEqual(game.rom(), patched.resolve())
            with self.assertRaisesRegex(LocalConfigError, "base ROM does not exist"):
                game.rom(base=True)

    def test_rejects_unknown_game_and_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "games.toml"
            config.write_text(
                """
[games.test-game]
patched_rom = "patched.nds"
unexpected = true
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(LocalConfigError, "Unknown fields"):
                LocalGameRegistry.load(config)


class CliInputResolutionTests(unittest.TestCase):
    def test_resolves_configured_game_and_base_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            base = root / "base.nds"
            patched.touch()
            base.touch()
            config = root / "games.toml"
            config.write_text(
                """
[games.test-game]
patched_rom = "patched.nds"
base_rom = "base.nds"
""".strip(),
                encoding="utf-8",
            )
            patched_args = build_parser().parse_args(
                ["inspect", "--game", "test-game", "--games-config", str(config)]
            )
            base_args = build_parser().parse_args(
                [
                    "inspect",
                    "--game",
                    "test-game",
                    "--base",
                    "--games-config",
                    str(config),
                ]
            )

            self.assertEqual(_resolve_input_rom(patched_args), patched.resolve())
            self.assertEqual(_resolve_input_rom(base_args), base.resolve())

    def test_preserves_positional_input_and_supports_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "explicit.nds"
            rom.touch()
            positional = build_parser().parse_args(["inspect", str(rom)])
            optional = build_parser().parse_args(["inspect", "--rom", str(rom)])

            self.assertEqual(_resolve_input_rom(positional), rom.resolve())
            self.assertEqual(_resolve_input_rom(optional), rom.resolve())

    def test_rejects_conflicting_explicit_inputs(self) -> None:
        args = build_parser().parse_args(
            ["inspect", "positional.nds", "--rom", "override.nds"]
        )

        with self.assertRaisesRegex(LocalConfigError, "not both"):
            _resolve_input_rom(args)

    def test_configured_build_uses_base_rom_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            base = root / "base.nds"
            patched.touch()
            base.touch()
            config = root / "games.toml"
            config.write_text(
                "[games.test]\npatched_rom='patched.nds'\nbase_rom='base.nds'\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                ["build-game", "--game", "test", "--games-config", str(config)]
            )

            self.assertEqual(_resolve_build_baseline(args), base.resolve())

    def test_explicit_build_requires_base_or_hack_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "hack.nds"
            rom.touch()
            args = build_parser().parse_args(["build-moves", str(rom)])
            hack_only = build_parser().parse_args(
                ["build-moves", str(rom), "--hack-only"]
            )

            with self.assertRaisesRegex(LocalConfigError, "require --base-rom"):
                _resolve_build_baseline(args)
            self.assertIsNone(_resolve_build_baseline(hack_only))


if __name__ == "__main__":
    unittest.main()
