from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from romwiki.sites import SiteCatalog, build_sites
from romwiki.sites.mkdocs_hooks import _deployment_site_url
from romwiki.util.errors import SiteError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class SiteCatalogTests(unittest.TestCase):
    def test_loads_portal_and_game_sites_in_display_order(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        self.assertEqual(
            [site.id for site in catalog.sites],
            [
                "portal",
                "platinum",
                "renegade-platinum",
                "blaze-black-volt-white",
                "blaze-black-2-volt-white-2",
                "black-white",
            ],
        )
        self.assertEqual(catalog.get("renegade-platinum").slug, "renegade-platinum")
        renegade_platinum = catalog.get("renegade-platinum")
        self.assertEqual(renegade_platinum.theme, "platinum")
        game = renegade_platinum.game
        self.assertIsNotNone(game)
        assert game is not None
        self.assertEqual(game.creator, "Drayano")
        self.assertEqual(game.platform, "nintendo-ds")
        self.assertEqual(game.platform_name, "Nintendo DS")
        self.assertEqual(game.versions, ())
        black_white = catalog.get("black-white").game
        self.assertIsNotNone(black_white)
        assert black_white is not None
        self.assertEqual(black_white.versions, ("black", "white"))

    def test_build_all_targets_one_combined_artifact(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        commands: list[tuple[str, ...]] = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dist"

            # This test verifies multi-site command planning. Generated
            # content is intentionally absent in a clean CI checkout until
            # the deployment workflow restores the publication snapshot.
            with patch("romwiki.sites.build._validate_generated_content"):
                built = build_sites(
                    catalog,
                    output,
                    build_all=True,
                    runner=lambda command: commands.append(tuple(command)),
                )

            self.assertEqual(
                [site.id for site in built],
                [
                    "portal",
                    "platinum",
                    "renegade-platinum",
                    "blaze-black-volt-white",
                    "blaze-black-2-volt-white-2",
                    "black-white",
                ],
            )
            self.assertEqual(Path(commands[0][-1]), output.resolve())
            self.assertEqual(Path(commands[1][-1]), output.resolve() / "platinum")
            self.assertEqual(
                Path(commands[2][-1]), output.resolve() / "renegade-platinum"
            )
            self.assertEqual(
                Path(commands[3][-1]),
                output.resolve() / "blaze-black-volt-white",
            )
            self.assertEqual(
                Path(commands[4][-1]),
                output.resolve() / "blaze-black-2-volt-white-2",
            )
            self.assertEqual(Path(commands[5][-1]), output.resolve() / "black-white")

    def test_documentation_only_site_does_not_require_profiles(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        site = catalog.get("blaze-black-2-volt-white-2")

        self.assertIsNotNone(site.game)
        assert site.game is not None
        self.assertFalse(site.game.data_driven)
        self.assertEqual(site.game.profiles, ())

    def test_build_requires_an_explicit_selection(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        with self.assertRaises(SiteError):
            build_sites(catalog, Path("dist"), runner=lambda command: None)

    def test_deployment_urls_preserve_the_pages_repository_path(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        self.assertEqual(
            _deployment_site_url(
                "https://example.test/rom-wiki", catalog.get("portal")
            ),
            "https://example.test/rom-wiki/",
        )
        self.assertEqual(
            _deployment_site_url(
                "https://example.test/rom-wiki/",
                catalog.get("renegade-platinum"),
            ),
            "https://example.test/rom-wiki/renegade-platinum/",
        )

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
[appearance]
theme = "portal"
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
platform_name = "Nintendo DS"
creator = "Tester"
[appearance]
theme = "missing-theme"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaises(SiteError):
                SiteCatalog.load(root)


if __name__ == "__main__":
    unittest.main()
