from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path

from mkdocs.config import load_config
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page

from romwiki.sites import mkdocs_hooks
from romwiki.util.errors import SiteError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PORTAL_CONFIG = REPOSITORY_ROOT / "sites/portal/mkdocs.yml"
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
    def test_portal_build_writes_shared_game_catalog(self) -> None:
        config = _load_and_configure(PORTAL_CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            config.site_dir = directory
            mkdocs_hooks.on_post_build(config)
            content = (Path(directory) / "games.json").read_bytes()
            catalog = json.loads(content.decode("utf-8"))

        self.assertNotIn(b"\r", content)
        self.assertEqual(catalog["schema_version"], 1)
        self.assertIn("renegade-platinum", {game["id"] for game in catalog["games"]})

    def test_portal_homepage_toc_lists_catalog_generations(self) -> None:
        config = _load_and_configure(PORTAL_CONFIG)
        file = File(
            "index.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        page = Page("ROM Wiki", file, config)

        mkdocs_hooks._add_site_context({}, page, config, nav=None)

        games = page.toc.items[0]
        generations = sorted(
            {game["generation"] for game in config.extra["romwiki_games"]}
        )
        self.assertEqual(
            (games.title, games.id, games.level), ("Game wikis", "games-heading", 2)
        )
        self.assertEqual(
            [(item.title, item.id, item.level) for item in games.children],
            [
                (
                    f"Generation {generation}",
                    f"generation-{generation}-heading",
                    3,
                )
                for generation in generations
            ],
        )

    def test_rewrites_links_to_pages_filtered_from_dev_build(self) -> None:
        html = (
            '<a href="../pokemon/buneary.md">Buneary</a>'
            '<a href="../moves/tackle.md#effects">Effects</a>'
            '<a href="https://example.test/readme.md">External</a>'
        )

        rewritten = mkdocs_hooks._rewrite_filtered_markdown_links(
            html,
            "abilities/klutz.md",
            "abilities/klutz/",
        )

        self.assertIn('href="../../pokemon/buneary/"', rewritten)
        self.assertIn('href="../../moves/tackle/#effects"', rewritten)
        self.assertIn('href="https://example.test/readme.md"', rewritten)

    def test_on_page_content_leaves_production_html_unchanged(self) -> None:
        config = _load_and_configure(GAME_CONFIG)
        file = File(
            "abilities/klutz.md",
            config.docs_dir,
            config.site_dir,
            config.use_directory_urls,
        )
        page = Page("Klutz", file, config)
        html = '<a href="../abilities/klutz.md#effects">Effects</a>'

        rendered = mkdocs_hooks.on_page_content(
            html,
            page,
            config,
            Files([file]),
        )

        self.assertEqual(rendered, html)

    def test_on_config_registers_only_the_current_game_for_fallback(self) -> None:
        config = _load_and_configure(GAME_CONFIG)

        site = config.extra["romwiki_site"]
        self.assertEqual(site["id"], "renegade-platinum")
        self.assertEqual(site["kind"], "game")

        games = config.extra["romwiki_games"]
        self.assertEqual(
            [game["id"] for game in games],
            ["renegade-platinum"],
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

        context = mkdocs_hooks._add_site_context({}, page, config, nav=None)

        self.assertEqual(context["romwiki"]["current"]["id"], "renegade-platinum")
        self.assertEqual(
            [game["id"] for game in context["romwiki"]["games"]],
            ["renegade-platinum"],
        )
        self.assertTrue(context["romwiki"]["games"][0]["url"].endswith("/"))

    def test_search_indexes_generated_record_pages_by_title_only(self) -> None:
        content = (
            '<h1 id="garchomp">Garchomp</h1>'
            '<section class="rw-summary"><div><p>Mach Pokémon</p></div>'
            "<p>Hero text</p></section>"
            '<h2 id="base-stats">Base stats</h2><table><tr><td>HP</td></tr></table>'
        )

        page, entries = self._index_page("pokemon/garchomp.md", "Garchomp", content)

        self.assertEqual(
            entries,
            [{"location": "pokemon/garchomp/", "title": "Garchomp", "text": ""}],
        )
        self.assertEqual(page.content, content)

    def test_search_fully_indexes_section_and_handwritten_pages(self) -> None:
        content = (
            '<h1 id="pokemon">Pokémon</h1><p>Browse species.</p>'
            '<h2 id="notes">Notes</h2><p>Details.</p>'
        )
        for src_uri in ("pokemon/index.md", "data-sources.md", "guides/pokemon.md"):
            with self.subTest(src_uri=src_uri):
                page, entries = self._index_page(src_uri, "Pokémon", content)

                self.assertEqual(
                    [(entry["title"], entry["text"]) for entry in entries],
                    [
                        ("Pokémon", "<p>Browse species.</p>"),
                        ("Notes", "<p>Details.</p>"),
                    ],
                )
                self.assertEqual(page.content, content)

    def _index_page(
        self, src_uri: str, title: str, content: str
    ) -> tuple[Page, list[dict[str, str]]]:
        # Runs the real plugin event chain so the hook's ordering around
        # Material's search plugin is exercised, not just the hook functions.
        config = load_config(config_file=str(GAME_CONFIG))
        config = config.plugins.on_config(config)
        file = File(
            src_uri, config.docs_dir, config.site_dir, config.use_directory_urls
        )
        page = Page(title, file, config)
        page.content = content

        config.plugins.on_page_context({}, page=page, config=config, nav=None)

        search = config.plugins["material/search"]
        return page, search.search_index.entries


if __name__ == "__main__":
    unittest.main()
