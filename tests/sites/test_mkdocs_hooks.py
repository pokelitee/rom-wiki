from __future__ import annotations

import types
import unittest
from pathlib import Path

from mkdocs.config import load_config
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page

from romwiki.sites import mkdocs_hooks
from romwiki.util.errors import SiteError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GAME_CONFIG = REPOSITORY_ROOT / "sites/games/renegade-platinum/mkdocs.yml"
DEV_CONFIG = REPOSITORY_ROOT / "sites/games/renegade-platinum/mkdocs.dev.yml"


def _load_and_configure(config_path: Path):
    # mkdocs' `hooks:` plugin loads the hook file as a standalone module
    # copy, isolated from `romwiki.sites.mkdocs_hooks`'s own module globals.
    # Calling `on_config` directly (rather than via `config.plugins.run_event`)
    # exercises the function against our imported module's state instead.
    config = load_config(config_file=str(config_path))
    return mkdocs_hooks.on_config(config)


class MkDocsHooksTests(unittest.TestCase):
    def test_on_config_registers_current_site_and_published_games(self) -> None:
        config = _load_and_configure(GAME_CONFIG)

        site = config.extra["romwiki_site"]
        self.assertEqual(site["id"], "renegade-platinum")
        self.assertEqual(site["kind"], "game")

        games = config.extra["romwiki_games"]
        self.assertEqual(
            [game["id"] for game in games],
            [
                "platinum-us",
                "renegade-platinum",
                "blaze-black-volt-white",
                "black-white",
            ],
        )

    def test_on_config_loads_dev_pages_from_configured_manifest(self) -> None:
        _load_and_configure(DEV_CONFIG)

        self.assertIsNotNone(mkdocs_hooks._dev_pages)
        assert mkdocs_hooks._dev_pages is not None
        self.assertIn("bulbasaur", mkdocs_hooks._dev_pages.pages_for("pokemon"))

    def test_on_config_rejects_a_config_not_registered_in_any_site(self) -> None:
        fake_config = types.SimpleNamespace(
            config_file_path=str(GAME_CONFIG.parent / "mkdocs.unregistered.yml"),
            extra={},
        )

        with self.assertRaises(SiteError):
            mkdocs_hooks.on_config(fake_config)

    def test_on_files_keeps_all_files_when_no_dev_pages_are_configured(self) -> None:
        config = _load_and_configure(GAME_CONFIG)
        files = Files(
            [
                File(
                    "pokemon/bulbasaur.md",
                    config.docs_dir,
                    config.site_dir,
                    config.use_directory_urls,
                )
            ]
        )

        filtered = mkdocs_hooks.on_files(files, config)

        self.assertEqual(len(list(filtered)), 1)

    def test_on_files_filters_out_pages_missing_from_dev_pages(self) -> None:
        config = _load_and_configure(DEV_CONFIG)
        included = File(
            "pokemon/bulbasaur.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        excluded = File(
            "pokemon/not-a-dev-page.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        always_kept = File(
            "pokemon/index.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        files = Files([included, excluded, always_kept])

        filtered = mkdocs_hooks.on_files(files, config)

        self.assertEqual(
            sorted(file.src_uri for file in filtered),
            ["pokemon/bulbasaur.md", "pokemon/index.md"],
        )

    def test_on_page_context_injects_current_site_and_game_links(self) -> None:
        config = _load_and_configure(GAME_CONFIG)
        file = File(
            "pokemon/bulbasaur.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        page = Page("Bulbasaur", file, config)

        context = mkdocs_hooks.on_page_context({}, page, config, nav=None)

        self.assertEqual(context["romwiki"]["current"]["id"], "renegade-platinum")
        self.assertEqual(
            [game["id"] for game in context["romwiki"]["games"]],
            [
                "platinum-us",
                "renegade-platinum",
                "blaze-black-volt-white",
                "black-white",
            ],
        )
        self.assertTrue(context["romwiki"]["games"][0]["url"].endswith("/"))


if __name__ == "__main__":
    unittest.main()
