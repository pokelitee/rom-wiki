from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from romwiki.sites import SiteCatalog
from romwiki.sites.catalog import _load_game_metadata, _validate_profile_references
from romwiki.util.errors import SiteError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class SiteCatalogTests(unittest.TestCase):
    def test_data_driven_site_can_declare_a_truthful_vertical_slice(self) -> None:
        metadata = _load_game_metadata(
            Path("sites/games/future/game.toml"),
            Path("."),
            {
                "profile": "future-game",
                "generation": 6,
                "base_game": "future-game",
                "platform": "future-platform",
                "platform_name": "Future Platform",
                "creator": "Game Studio",
                "generated_sections": [
                    "pokemon",
                    "abilities",
                    "types",
                ],
            },
        )

        self.assertTrue(metadata.data_driven)
        self.assertEqual(
            metadata.generated_sections,
            ("pokemon", "abilities", "types"),
        )

    def test_loads_portal_and_game_sites_in_display_order(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        self.assertEqual(
            [site.id for site in catalog.sites],
            [
                "portal",
                "firered-leafgreen",
                "emerald",
                "platinum",
                "renegade-platinum",
                "heart-gold-soul-silver",
                "sacred-gold-storm-silver",
                "black-white",
                "blaze-black-volt-white",
                "black-2-white-2",
                "blaze-black-2-volt-white-2",
                "blaze-black-2-redux-volt-white-2-redux",
            ],
        )
        self.assertEqual(catalog.get("renegade-platinum").slug, "renegade-platinum")
        self.assertEqual(catalog.get("platinum").order, 10)
        self.assertEqual(catalog.get("black-white").order, 10)
        renegade_platinum = catalog.get("renegade-platinum")
        self.assertEqual(renegade_platinum.theme, "platinum")
        self.assertEqual(
            catalog.get("heart-gold-soul-silver").theme,
            "heart-gold-soul-silver",
        )
        self.assertEqual(
            catalog.get("black-2-white-2").theme,
            "black-2-white-2",
        )
        self.assertEqual(catalog.get("firered-leafgreen").theme, "firered-leafgreen")
        self.assertEqual(catalog.get("emerald").theme, "emerald")
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
        black_2_white_2 = catalog.get("black-2-white-2").game
        self.assertIsNotNone(black_2_white_2)
        assert black_2_white_2 is not None
        self.assertEqual(black_2_white_2.versions, ("black-2", "white-2"))
        hgss = catalog.get("heart-gold-soul-silver")
        self.assertTrue(hgss.published)
        self.assertIsNotNone(hgss.game)
        assert hgss.game is not None
        self.assertTrue(hgss.game.data_driven)
        self.assertEqual(hgss.game.profiles, ("heartgold-us", "soulsilver-us"))
        self.assertEqual(
            hgss.game.generated_sections,
            (
                "pokemon",
                "abilities",
                "moves",
                "items",
                "encounters",
                "trainers",
                "locations",
                "types",
            ),
        )
        sacred_gold_storm_silver = catalog.get("sacred-gold-storm-silver")
        self.assertTrue(sacred_gold_storm_silver.published)
        self.assertIsNotNone(sacred_gold_storm_silver.game)
        assert sacred_gold_storm_silver.game is not None
        self.assertTrue(sacred_gold_storm_silver.game.data_driven)
        self.assertEqual(
            sacred_gold_storm_silver.game.profiles,
            ("sacred-gold", "storm-silver"),
        )
        self.assertEqual(
            sacred_gold_storm_silver.game.generated_sections,
            hgss.game.generated_sections,
        )

    def test_b2w2_site_uses_paired_hack_profiles(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        site = catalog.get("blaze-black-2-volt-white-2")

        self.assertIsNotNone(site.game)
        assert site.game is not None
        self.assertTrue(site.game.data_driven)
        self.assertEqual(
            site.game.profiles,
            ("blaze-black-2", "volt-white-2"),
        )

        redux = catalog.get("blaze-black-2-redux-volt-white-2-redux")
        self.assertIsNotNone(redux.game)
        assert redux.game is not None
        self.assertTrue(redux.game.data_driven)
        self.assertEqual(
            redux.game.profiles,
            ("blaze-black-2-redux", "volt-white-2-redux"),
        )

    def test_rejects_generation_that_does_not_match_profile_engine(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        site = catalog.get("platinum")
        self.assertIsNotNone(site.game)
        assert site.game is not None
        self.assertIsNotNone(catalog.profile_repository)
        mismatched = replace(site, game=replace(site.game, generation=5))

        with self.assertRaisesRegex(SiteError, "generation does not match"):
            _validate_profile_references(
                (mismatched,),
                catalog.profile_repository,
            )

    def test_generated_sections_must_match_profile_capabilities(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        site = catalog.get("platinum")
        self.assertIsNotNone(site.game)
        assert site.game is not None
        self.assertIsNotNone(catalog.profile_repository)
        incomplete = replace(
            site,
            game=replace(
                site.game,
                generated_sections=tuple(
                    section
                    for section in site.game.generated_sections
                    if section != "trainers"
                ),
            ),
        )

        with self.assertRaisesRegex(
            SiteError,
            "generated_sections do not match",
        ):
            _validate_profile_references(
                (incomplete,),
                catalog.profile_repository,
            )

    def test_rejects_invalid_game_appearance_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            portal = root / "sites" / "portal"
            game = root / "sites" / "games" / "test-game"
            portal.mkdir(parents=True)
            game.mkdir(parents=True)
            (portal / "site.toml").write_text(
                """
[site]
id = "portal"
name = "Portal"
kind = "portal"
slug = ""
published = true
order = 0
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


class AuthoredMarkdownTests(unittest.TestCase):
    def test_authored_markdown_avoids_mkdocs_only_blocks(self) -> None:
        # The React app renders GitHub-flavored Markdown, which would show
        # MkDocs tabs and admonitions as literal or indented-code text.
        mkdocs_block = re.compile(r'^(?:=== "|!!! |\?\?\?\+? )')
        offenders = [
            f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{number}"
            for path in sorted((REPOSITORY_ROOT / "sites").rglob("*.md"))
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if mkdocs_block.match(line)
        ]

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
