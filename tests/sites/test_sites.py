from __future__ import annotations

import tempfile
import threading
import time
import unittest
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.sites import SiteCatalog, build_sites
from romwiki.sites.build import _run_command, _validate_generated_content
from romwiki.sites.catalog import _load_game_metadata, _validate_profile_references
from romwiki.sites.mkdocs_hooks import _deployment_site_url
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
                    "data",
                ],
            },
        )

        self.assertTrue(metadata.data_driven)
        self.assertEqual(
            metadata.generated_sections,
            ("pokemon", "abilities", "types", "data"),
        )

    def test_build_command_can_set_the_combined_site_url(self) -> None:
        with patch("romwiki.sites.build.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="")
            _run_command(("python", "-m", "mkdocs"), site_url="http://localhost:8000/")

        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["ROMWIKI_SITE_URL"], "http://localhost:8000/")

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
                "black-2-white-2",
                "heart-gold-soul-silver",
                "sacred-gold-storm-silver",
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
                "data",
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

    def test_build_all_targets_one_combined_artifact(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        commands: list[tuple[str, ...]] = []
        lock = threading.Lock()

        def record(command: Sequence[str]) -> None:
            with lock:
                commands.append(tuple(command))

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
                    runner=record,
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
                    "black-2-white-2",
                    "heart-gold-soul-silver",
                    "sacred-gold-storm-silver",
                ],
            )
            # Game builds run concurrently, so only their destinations are
            # guaranteed -- not the order the commands were issued in.
            self.assertEqual(
                {Path(command[-1]) for command in commands},
                {
                    output.resolve(),
                    output.resolve() / "platinum",
                    output.resolve() / "renegade-platinum",
                    output.resolve() / "blaze-black-volt-white",
                    output.resolve() / "blaze-black-2-volt-white-2",
                    output.resolve() / "black-white",
                    output.resolve() / "black-2-white-2",
                    output.resolve() / "heart-gold-soul-silver",
                    output.resolve() / "sacred-gold-storm-silver",
                },
            )
            # The portal renders into the artifact root, and MkDocs `--clean`
            # empties that directory, so it must finish before any game build
            # writes a subdirectory into it.
            self.assertEqual(Path(commands[0][-1]), output.resolve())

    def test_dev_build_uses_game_dev_configs_and_the_portal_config(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        commands: list[tuple[str, ...]] = []
        lock = threading.Lock()

        def record(command: Sequence[str]) -> None:
            with lock:
                commands.append(tuple(command))

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("romwiki.sites.build._validate_generated_content"),
        ):
            built = build_sites(
                catalog,
                Path(directory),
                build_all=True,
                dev=True,
                runner=record,
            )

        # Concurrent game builds record commands out of order, so each command
        # is matched back to its site by the destination it renders into.
        destinations = {
            site.output_path(Path(directory).resolve()): site.id for site in built
        }
        configs = {
            destinations[Path(command[-1])]: Path(
                command[command.index("--config-file") + 1]
            )
            for command in commands
        }
        self.assertEqual(configs["portal"].name, "mkdocs.yml")
        for site in built:
            if site.kind == "game":
                self.assertEqual(configs[site.id].name, "mkdocs.dev.yml")

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

    def test_generated_content_validation_honors_declared_sections(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        site = catalog.get("platinum")
        self.assertIsNotNone(site.game)
        assert site.game is not None
        sections = (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "types",
            "data",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "mkdocs.yml"
            config.write_text("site_name: Partial\n", encoding="utf-8")
            partial = replace(
                site,
                config_path=config,
                game=replace(site.game, generated_sections=sections),
            )
            for section in sections:
                index = root / "wiki" / section / "index.md"
                index.parent.mkdir(parents=True)
                index.write_text(f"# {section}\n", encoding="utf-8")

            _validate_generated_content(partial)

    def test_root_site_finishes_before_any_nested_build_starts(self) -> None:
        # MkDocs `--clean` empties the artifact root, so the portal must not
        # overlap the game builds that write subdirectories into it.
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        lock = threading.Lock()
        running = 0
        overlapped_with_root = False
        root_finished = False

        def record(command: Sequence[str]) -> None:
            nonlocal running, overlapped_with_root, root_finished
            is_root = Path(command[-1]) == Path("dist").resolve()
            with lock:
                if is_root and running > 0:
                    overlapped_with_root = True
                if not is_root and not root_finished:
                    overlapped_with_root = True
                running += 1
            time.sleep(0.05)
            with lock:
                running -= 1
                if is_root:
                    root_finished = True

        with patch("romwiki.sites.build._validate_generated_content"):
            build_sites(catalog, Path("dist"), build_all=True, runner=record)

        self.assertTrue(root_finished)
        self.assertFalse(overlapped_with_root)

    def test_a_failing_site_build_propagates_and_awaits_siblings(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        lock = threading.Lock()
        finished: list[str] = []

        def record(command: Sequence[str]) -> None:
            destination = Path(command[-1]).name
            if destination == "platinum":
                raise SiteError("MkDocs build failed with exit code 1")
            time.sleep(0.05)
            with lock:
                finished.append(destination)

        with (
            patch("romwiki.sites.build._validate_generated_content"),
            self.assertRaises(SiteError),
        ):
            build_sites(catalog, Path("dist"), build_all=True, runner=record)

        # Every sibling still ran to completion rather than being abandoned
        # mid-flight when one build raised.
        self.assertEqual(
            set(finished),
            {
                "dist",
                "renegade-platinum",
                "blaze-black-volt-white",
                "blaze-black-2-volt-white-2",
                "black-white",
                "black-2-white-2",
                "heart-gold-soul-silver",
                "sacred-gold-storm-silver",
            },
        )

    def test_rejects_a_job_count_below_one(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        with (
            patch("romwiki.sites.build._validate_generated_content"),
            self.assertRaises(SiteError),
        ):
            build_sites(
                catalog,
                Path("dist"),
                build_all=True,
                jobs=0,
                runner=lambda command: None,
            )

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
