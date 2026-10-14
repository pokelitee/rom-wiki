from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.pipeline.build.regeneration import (
    can_reuse_generation,
    regeneration_fingerprint,
    write_regeneration_state,
)
from romwiki.sites.catalog import GameMetadata, SiteDefinition


class RegenerationStateTests(unittest.TestCase):
    def test_development_fingerprint_tracks_mode_and_page_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "site"
            site_root.mkdir()
            (site_root / "game.toml").write_text("[game]\n", encoding="utf-8")
            manifest = site_root / "dev-pages.toml"
            manifest.write_text("[pages]\n", encoding="utf-8")
            site = _site(site_root)
            result = SimpleNamespace(
                match=SimpleNamespace(
                    profile=SimpleNamespace(engine="test", id="game")
                ),
                image=SimpleNamespace(hashes=SimpleNamespace(sha256="rom")),
            )

            with patch(
                "romwiki.pipeline.build.regeneration.profile_fingerprint",
                return_value="profile",
            ):
                production = regeneration_fingerprint(root, site, (result,), (), root)
                development = regeneration_fingerprint(
                    root, site, (result,), (), root, dev=True
                )
                manifest.write_text(
                    '[pages]\npokemon = ["bulbasaur"]\n', encoding="utf-8"
                )
                changed = regeneration_fingerprint(
                    root, site, (result,), (), root, dev=True
                )

        self.assertNotEqual(production, development)
        self.assertNotEqual(development, changed)

    def test_fingerprint_tracks_every_package_source_module(self) -> None:
        modules = (
            "sources/pokedb.py",
            "util/text.py",
            "engines/registry.py",
            "sites/catalog.py",
            "pipeline/build/regeneration.py",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = _site_with_game_toml(root)
            package_root = root / "src" / "romwiki"
            for module in modules:
                path = package_root / module
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("VALUE = 1\n", encoding="utf-8")

            def fingerprint() -> str:
                return regeneration_fingerprint(root, site, (), (), root / "pokedb")

            baseline = fingerprint()
            for module in modules:
                with self.subTest(module=module):
                    path = package_root / module
                    path.write_text("VALUE = 22\n", encoding="utf-8")
                    self.assertNotEqual(fingerprint(), baseline)
                    path.write_text("VALUE = 1\n", encoding="utf-8")
                    self.assertEqual(fingerprint(), baseline)

            (package_root / "util" / "new_helper.py").write_text("", encoding="utf-8")
            self.assertNotEqual(fingerprint(), baseline)

    def test_fingerprint_tracks_pokedb_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = _site_with_game_toml(root)
            pokedb = root / "pokedb"
            pokedb.mkdir()
            data = pokedb / "pokemon.json"
            data.write_text("[]", encoding="utf-8")

            before = regeneration_fingerprint(root, site, (), (), pokedb)
            data.write_text('[{"id": 1}]', encoding="utf-8")
            after = regeneration_fingerprint(root, site, (), (), pokedb)

        self.assertNotEqual(before, after)

    def test_digest_cache_reuses_unchanged_files_without_changing_the_value(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = _site_with_game_toml(root)
            module = root / "src" / "romwiki" / "module.py"
            module.parent.mkdir(parents=True)
            module.write_text("VALUE = 1\n", encoding="utf-8")
            pokedb = root / "pokedb"
            pokedb.mkdir()
            (pokedb / "pokemon.json").write_text("[]", encoding="utf-8")
            digest_cache = root / ".romwiki" / "file-digests.json"

            def fingerprint(cache: Path | None) -> str:
                return regeneration_fingerprint(
                    root, site, (), (), pokedb, digest_cache=cache
                )

            uncached = fingerprint(None)
            self.assertEqual(fingerprint(digest_cache), uncached)
            with patch(
                "romwiki.pipeline.build.regeneration._cached_file_digest"
            ) as file_digest:
                self.assertEqual(fingerprint(digest_cache), uncached)
            file_digest.assert_not_called()

            module.write_text("VALUE = 22\n", encoding="utf-8")
            self.assertEqual(fingerprint(digest_cache), fingerprint(None))
            self.assertNotEqual(fingerprint(digest_cache), uncached)

    def test_digest_cache_drops_deleted_files_but_keeps_other_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = _site_with_game_toml(root)
            pokedb = root / "pokedb"
            for generation in ("gen4", "gen5"):
                (pokedb / generation).mkdir(parents=True)
                (pokedb / generation / "pokemon.json").write_text(
                    "[]", encoding="utf-8"
                )
            removed = pokedb / "gen4" / "moves.json"
            removed.write_text("[]", encoding="utf-8")
            digest_cache = root / "file-digests.json"
            regeneration_fingerprint(
                root, site, (), (), pokedb / "gen5", digest_cache=digest_cache
            )
            regeneration_fingerprint(
                root, site, (), (), pokedb / "gen4", digest_cache=digest_cache
            )
            removed.unlink()

            regeneration_fingerprint(
                root, site, (), (), pokedb / "gen4", digest_cache=digest_cache
            )

            cached = json.loads(digest_cache.read_text(encoding="utf-8"))["files"]
            self.assertIn(str((pokedb / "gen5" / "pokemon.json").absolute()), cached)
            self.assertIn(str((pokedb / "gen4" / "pokemon.json").absolute()), cached)
            self.assertNotIn(str(removed.absolute()), cached)

    def test_reuses_only_an_exact_generated_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "site"
            generated = site_root / "wiki" / "pokemon" / "index.md"
            generated.parent.mkdir(parents=True)
            generated.write_text("# Pokemon\n", encoding="utf-8")
            site = _site(site_root)
            state = root / "state.json"
            write_regeneration_state(state, "input", site)

            self.assertTrue(can_reuse_generation(state, "input", site))
            generated.write_text("changed\n", encoding="utf-8")
            self.assertFalse(can_reuse_generation(state, "input", site))
            self.assertFalse(can_reuse_generation(state, "other", site))


def _site_with_game_toml(root: Path) -> SiteDefinition:
    site_root = root / "site"
    site_root.mkdir()
    (site_root / "game.toml").write_text("[game]\n", encoding="utf-8")
    return _site(site_root)


def _site(site_root: Path) -> SiteDefinition:
    return SiteDefinition(
        "game",
        "Game",
        "game",
        "game",
        True,
        1,
        site_root / "mkdocs.yml",
        "",
        "platinum",
        GameMetadata(
            ("game",), (), True, 4, "base", "nds", "NDS", "Test", ("pokemon",)
        ),
    )


if __name__ == "__main__":
    unittest.main()
