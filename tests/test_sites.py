from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.errors import SiteError
from romwiki.sites import SiteCatalog, build_sites


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SiteCatalogTests(unittest.TestCase):
    def test_loads_portal_and_game_sites_in_display_order(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        self.assertEqual(
            [site.id for site in catalog.sites],
            ["portal", "renegade-platinum"],
        )
        self.assertEqual(catalog.get("renegade-platinum").slug, "renegade-platinum")
        game = catalog.get("renegade-platinum").game
        self.assertIsNotNone(game)
        assert game is not None
        self.assertEqual(game.creator, "Drayano")
        self.assertEqual(game.platform, "nintendo-ds")
        self.assertEqual(game.theme, "platinum")

    def test_build_all_targets_one_combined_artifact(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        commands: list[tuple[str, ...]] = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dist"

            built = build_sites(
                catalog,
                output,
                build_all=True,
                runner=lambda command: commands.append(tuple(command)),
            )

            self.assertEqual([site.id for site in built], ["portal", "renegade-platinum"])
            self.assertEqual(Path(commands[0][-1]), output.resolve())
            self.assertEqual(
                Path(commands[1][-1]), output.resolve() / "renegade-platinum"
            )

    def test_build_requires_an_explicit_selection(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        with self.assertRaises(SiteError):
            build_sites(catalog, Path("dist"), runner=lambda command: None)

    def test_rejects_invalid_game_appearance_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            portal = root / "sites" / "portal"
            game = root / "sites" / "games" / "test-game"
            portal.mkdir(parents=True)
            game.mkdir(parents=True)
            (portal / "mkdocs.yml").write_text("site_name: Portal\n", encoding="utf-8")
            (game / "mkdocs.yml").write_text("site_name: Game\n", encoding="utf-8")
            (portal / "site.toml").write_text(
                """
[site]
id = "portal"
name = "Portal"
kind = "portal"
slug = ""
published = true
order = 0
mkdocs_config = "mkdocs.yml"
description = "Portal"
""".strip(),
                encoding="utf-8",
            )
            (game / "game.toml").write_text(
                """
[site]
id = "test-game"
name = "Test Game"
kind = "game"
slug = "test-game"
published = true
order = 1
mkdocs_config = "mkdocs.yml"
description = "Test"
[game]
profile = "test-game"
generation = 4
base_game = "platinum"
platform = "nintendo-ds"
creator = "Tester"
[appearance]
theme = "Bad Theme"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaises(SiteError):
                SiteCatalog.load(root)


if __name__ == "__main__":
    unittest.main()
