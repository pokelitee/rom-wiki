from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from romwiki.sites.dev_pages import DevPages
from romwiki.util.errors import SiteError

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = (
    _REPOSITORY_ROOT / "sites" / "games" / "renegade-platinum" / "dev-pages.toml"
)


class DevPagesTests(unittest.TestCase):
    def test_loads_game_specific_page_selections(self) -> None:
        pages = DevPages.load(_MANIFEST)

        self.assertEqual(
            pages.pages_for("pokemon"),
            frozenset(
                {"bulbasaur", "eevee", "wurmple", "slowpoke", "deoxys-attack"}
            ),
        )
        self.assertEqual(pages.pages_for("generation-specific"), frozenset())

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
