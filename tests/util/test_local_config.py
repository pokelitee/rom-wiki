from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry


class LocalGameRegistryTests(unittest.TestCase):
    def test_resolves_relative_patched_and_base_paths_from_config_directory(
        self,
    ) -> None:
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


if __name__ == "__main__":
    unittest.main()
