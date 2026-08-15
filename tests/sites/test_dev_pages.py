from __future__ import annotations

import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mkdocs.config import load_config

from romwiki.sites import SiteCatalog
from romwiki.sites.dev_pages import DevPages
from romwiki.util.errors import SiteError

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_GAME_SITES = _REPOSITORY_ROOT / "sites" / "games"
_MANIFEST = _GAME_SITES / "renegade-platinum" / "dev-pages.toml"
_DETAIL_SECTIONS = {
    "pokemon",
    "abilities",
    "moves",
    "items",
    "encounters",
    "trainers",
    "locations",
}


class DevPagesTests(unittest.TestCase):
    def test_loads_game_specific_page_selections(self) -> None:
        pages = DevPages.load(_MANIFEST)

        self.assertEqual(
            pages.pages_for("pokemon"),
            frozenset(
                {
                    "arbok",
                    "bulbasaur",
                    "eevee",
                    "wurmple",
                    "slowpoke",
                    "deoxys-attack",
                }
            ),
        )
        self.assertEqual(pages.pages_for("generation-specific"), frozenset())

    def test_all_game_manifests_cover_their_generated_detail_sections(self) -> None:
        manifests = sorted(_GAME_SITES.glob("*/dev-pages.toml"))
        catalog = SiteCatalog.load(_REPOSITORY_ROOT)

        self.assertTrue(manifests)
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                pages = DevPages.load(manifest)
                site = catalog.get(manifest.parent.name)
                assert site.game is not None
                expected = set(site.game.generated_sections) & _DETAIL_SECTIONS
                self.assertEqual(set(pages.sections), expected)
                self.assertTrue(all(pages.sections.values()))

    def test_all_game_dev_configs_load_their_page_manifest(self) -> None:
        for manifest in sorted(_GAME_SITES.glob("*/dev-pages.toml")):
            with self.subTest(manifest=manifest):
                config = load_config(
                    config_file=str(manifest.with_name("mkdocs.dev.yml"))
                )
                self.assertEqual(config.extra.get("romwiki_dev_pages"), manifest.name)
                self.assertEqual(config.validation.links.not_found, logging.DEBUG)

    def test_selected_detail_pages_exist_in_the_generated_source_tree(self) -> None:
        for manifest in sorted(_GAME_SITES.glob("*/dev-pages.toml")):
            pages = DevPages.load(manifest)
            with self.subTest(manifest=manifest):
                missing = sorted(
                    f"{section}/{slug}.md"
                    for section, slugs in pages.sections.items()
                    for slug in slugs
                    if not (manifest.parent / "wiki" / section / f"{slug}.md").is_file()
                )
                self.assertEqual(missing, [])

    def test_filters_only_configured_section_detail_pages(self) -> None:
        pages = DevPages.load(_MANIFEST)

        self.assertTrue(pages.includes_document("pokemon/index.md"))
        self.assertTrue(pages.includes_document("pokemon/bulbasaur.md"))
        self.assertFalse(pages.includes_document("pokemon/charmander.md"))
        self.assertTrue(pages.includes_document("changes/pokemon.md"))
        self.assertTrue(pages.includes_document("data-sources.md"))

    def test_rejects_invalid_page_slugs(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dev-pages.toml"
            path.write_text('[pages]\npokemon = ["../outside"]\n', encoding="utf-8")

            with self.assertRaises(SiteError):
                DevPages.load(path)


if __name__ == "__main__":
    unittest.main()
