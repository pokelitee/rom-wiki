from __future__ import annotations

import json
import os
import tempfile
import unittest
from functools import cache
from pathlib import Path

from romwiki.sites.catalog import SiteCatalog
from romwiki.sites.frontend import export_frontend
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry
from romwiki.web_build import build_wiki

_ROOT = Path(__file__).resolve().parents[3]
_GAMES_CONFIG = _ROOT / ".local/games.toml"
_DATA_ROOT = _ROOT / "build/data"
_ENABLE = "ROMWIKI_ROM_TESTS"


@cache
def _pokedb(generation: int) -> PokeDBGeneration:
    root = LocalGameRegistry.load(_GAMES_CONFIG).pokedb_root
    assert root is not None
    return PokeDBGeneration.load(root / f"gen{generation}")


@unittest.skipUnless(
    os.environ.get(_ENABLE) == "1",
    f"real-ROM builds take minutes; set {_ENABLE}=1 to run them",
)
class BuildWikiTests(unittest.TestCase):
    """`build_wiki` must publish exactly what the repository export does.

    The export reads the checkout's generated data, so regenerate it
    (`romwiki generate --all`) before running this after a pipeline change.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not _GAMES_CONFIG.is_file():
            raise AssertionError(f"{_ENABLE}=1 requires {_GAMES_CONFIG}")
        cls.registry = LocalGameRegistry.load(_GAMES_CONFIG)
        if cls.registry.pokedb_root is None:
            raise AssertionError(f"{_ENABLE}=1 requires pokedb_root in {_GAMES_CONFIG}")

    registry: LocalGameRegistry

    def test_matches_the_export_for_every_single_rom_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "export"
            export_frontend(_ROOT, export, data_root=_DATA_ROOT)
            exported = json.loads((export / "manifest.json").read_text("utf-8"))
            entries = {game["id"]: game for game in exported["games"]}
            compared = 0
            for site in SiteCatalog.load(_ROOT).published():
                if site.game is None or len(site.game.profiles) != 1:
                    continue
                try:
                    paths = self.registry.get(site.game.profiles[0])
                    rom = paths.rom()
                    base_rom = (
                        paths.rom(base=True) if site.id != site.game.base_game else None
                    )
                except LocalConfigError:
                    continue
                with self.subTest(site=site.id):
                    files = build_wiki(
                        rom, root=_ROOT, pokedb=_pokedb, base_rom=base_rom
                    )
                    manifest = json.loads(files.pop("manifest.json"))
                    expected = {
                        path.relative_to(export).as_posix(): path.read_bytes()
                        for path in (export / site.id).rglob("*")
                        if path.is_file()
                    }
                    self.assertEqual(sorted(files), sorted(expected))
                    self.assertTrue(
                        all(files[path] == expected[path] for path in expected)
                    )
                    self.assertEqual(manifest["games"], [entries[site.id]])
                    self.assertTrue(manifest["local"]["verified"])
                compared += 1
        if compared == 0:
            self.fail(f"no single-ROM site in {_GAMES_CONFIG} has a local ROM")

    def test_builds_an_unknown_build_as_its_retail_game_unverified(self) -> None:
        try:
            rom = self.registry.get("firered-us").rom()
        except LocalConfigError:
            self.skipTest("firered-us has no local ROM")
        data = bytearray(rom.read_bytes())
        # The last byte is unused padding, so the copy reads the same as
        # FireRed but matches no known hash.
        data[-1] ^= 0xFF
        with tempfile.TemporaryDirectory() as directory:
            unknown = Path(directory) / "unknown.gba"
            unknown.write_bytes(data)
            files = build_wiki(unknown, root=_ROOT, pokedb=_pokedb, id_prefix="local-")

        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["local"]["profile"], "firered-us")
        self.assertFalse(manifest["local"]["verified"])
        game_id = manifest["games"][0]["id"]
        self.assertEqual(game_id, f"local-{manifest['local']['rom_sha256'][:12]}")
        self.assertTrue(
            all(
                path.startswith(f"{game_id}/")
                for path in files
                if path != "manifest.json"
            )
        )


if __name__ == "__main__":
    unittest.main()
