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

from romwiki.sites import GameMetadata, SiteCatalog, SiteDefinition, build_sites
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
                "firered-leafgreen",
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
                    "heart-gold-soul-silver",
                    "sacred-gold-storm-silver",
                    "black-white",
                    "blaze-black-volt-white",
                    "black-2-white-2",
                    "blaze-black-2-volt-white-2",
                    "blaze-black-2-redux-volt-white-2-redux",
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
                    output.resolve() / "blaze-black-2-redux-volt-white-2-redux",
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

    def test_incremental_build_reuses_output_and_cleans_after_a_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "sites" / "games" / "example"
            wiki_root = site_root / "wiki"
            wiki_root.mkdir(parents=True)
            config = site_root / "mkdocs.yml"
            config.write_text("site_name: Example\n", encoding="utf-8")
            index = wiki_root / "index.md"
            index.write_text("# Example\n", encoding="utf-8")
            site = SiteDefinition(
                id="example",
                name="Example",
                kind="game",
                slug="example",
                published=True,
                order=1,
                config_path=config,
                description="Example",
                theme="platinum",
                game=GameMetadata(
                    profiles=(),
                    versions=(),
                    data_driven=False,
                    generation=4,
                    base_game="platinum",
                    platform="nintendo-ds",
                    platform_name="Nintendo DS",
                    creator="Tester",
                ),
            )
            catalog = SiteCatalog(root, (site,))
            output = root / "dist"
            state_root = root / "state"
            commands: list[tuple[str, ...]] = []

            def build(command: Sequence[str]) -> None:
                commands.append(tuple(command))
                destination = Path(command[-1])
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "index.html").write_text("ok", encoding="utf-8")

            for _ in range(2):
                build_sites(
                    catalog,
                    output,
                    site_ids=(site.id,),
                    incremental=True,
                    state_root=state_root,
                    runner=build,
                )

            (output / site.slug / "index.html").unlink()
            build_sites(
                catalog,
                output,
                site_ids=(site.id,),
                incremental=True,
                state_root=state_root,
                runner=build,
            )
            config.write_text("site_name: Renamed Example\n", encoding="utf-8")
            build_sites(
                catalog,
                output,
                site_ids=(site.id,),
                incremental=True,
                state_root=state_root,
                runner=build,
            )
            added = wiki_root / "added.md"
            added.write_text("# Added\n", encoding="utf-8")
            build_sites(
                catalog,
                output,
                site_ids=(site.id,),
                incremental=True,
                state_root=state_root,
                runner=build,
            )
            added.unlink()
            build_sites(
                catalog,
                output,
                site_ids=(site.id,),
                incremental=True,
                state_root=state_root,
                runner=build,
            )

        self.assertEqual(len(commands), 5)
        self.assertIn("--clean", commands[0])
        self.assertIn("--clean", commands[1])
        self.assertIn("--clean", commands[2])
        self.assertIn("--dirty", commands[3])
        self.assertIn("--clean", commands[4])

    def test_complete_reuse_rebuilds_a_missing_portal_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            portal_root = root / "sites" / "portal"
            wiki_root = portal_root / "wiki"
            wiki_root.mkdir(parents=True)
            config = portal_root / "mkdocs.yml"
            config.write_text("site_name: Portal\n", encoding="utf-8")
            (wiki_root / "index.md").write_text("# Portal\n", encoding="utf-8")
            site = SiteDefinition(
                id="portal",
                name="Portal",
                kind="portal",
                slug=None,
                published=True,
                order=0,
                config_path=config,
                description="Portal",
                theme="portal",
                game=None,
            )
            catalog = SiteCatalog(root, (site,))
            output = root / "dist"
            commands: list[tuple[str, ...]] = []

            def build(command: Sequence[str]) -> None:
                commands.append(tuple(command))
                destination = Path(command[-1])
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "index.html").write_text("ok", encoding="utf-8")

            for _ in range(2):
                build_sites(
                    catalog,
                    output,
                    build_all=True,
                    reuse_unchanged=True,
                    defer_output_validation=True,
                    state_root=root / "state",
                    runner=build,
                )
                (output / "index.html").unlink()

        self.assertEqual(len(commands), 2)

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

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dist"

            def record(command: Sequence[str]) -> None:
                nonlocal running, overlapped_with_root, root_finished
                is_root = Path(command[-1]) == output.resolve()
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
                build_sites(catalog, output, build_all=True, runner=record)

        self.assertTrue(root_finished)
        self.assertFalse(overlapped_with_root)

    def test_root_site_reuses_existing_asset_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            portal_root = root / "sites" / "portal"
            game_root = root / "sites" / "games" / "example"
            portal_root.mkdir(parents=True)
            game_root.mkdir(parents=True)
            portal_config = portal_root / "mkdocs.yml"
            game_config = game_root / "mkdocs.yml"
            portal_config.write_text("site_name: Portal\n", encoding="utf-8")
            game_config.write_text("site_name: Example\n", encoding="utf-8")
            portal = SiteDefinition(
                "portal",
                "Portal",
                "portal",
                "",
                True,
                0,
                portal_config,
                "Portal",
                "portal",
            )
            game = SiteDefinition(
                "example",
                "Example",
                "game",
                "example",
                True,
                1,
                game_config,
                "Example",
                "platinum",
                GameMetadata((), (), False, 4, "platinum", "nds", "NDS", "Test"),
            )
            catalog = SiteCatalog(root, (portal, game))
            output = root / "dist"
            old_asset = output / "assets" / "javascripts" / "old.js"
            old_asset.parent.mkdir(parents=True)
            old_asset.write_text("old", encoding="utf-8")
            (output / "stale.html").write_text("stale", encoding="utf-8")
            nested_page = output / game.slug / "index.html"
            nested_page.parent.mkdir()
            nested_page.write_text("game", encoding="utf-8")

            def build(command: Sequence[str]) -> None:
                destination = Path(command[-1])
                asset = destination / "assets" / "javascripts" / "new.js"
                asset.parent.mkdir(parents=True)
                asset.write_text("new", encoding="utf-8")
                (destination / "index.html").write_text("portal", encoding="utf-8")

            # The former implementation required every old portal directory to
            # be removable before moving the staged directory into its place.
            with patch.object(Path, "rmdir", side_effect=PermissionError("in use")):
                build_sites(
                    catalog,
                    output,
                    site_ids=(portal.id,),
                    runner=build,
                )

            self.assertFalse(old_asset.exists())
            self.assertFalse((output / "stale.html").exists())
            self.assertEqual(
                (output / "assets" / "javascripts" / "new.js").read_text(
                    encoding="utf-8"
                ),
                "new",
            )
            self.assertEqual(nested_page.read_text(encoding="utf-8"), "game")

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
            tempfile.TemporaryDirectory() as directory,
            patch("romwiki.sites.build._validate_generated_content"),
            self.assertRaises(SiteError),
        ):
            build_sites(
                catalog, Path(directory) / "dist", build_all=True, runner=record
            )

        self.assertEqual(
            set(finished),
            {
                "dist",
                "renegade-platinum",
                "blaze-black-volt-white",
                "blaze-black-2-volt-white-2",
                "blaze-black-2-redux-volt-white-2-redux",
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
