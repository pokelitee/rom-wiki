from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from romwiki.cli import build_parser, main
from romwiki.cli.build import resolve_build_baseline
from romwiki.cli.common import (
    profile_wiki_root,
    resolve_input_rom,
    resolve_pokedb_path,
    resolve_pokedb_root,
    site_wiki_root,
    version_family_inputs,
    version_family_uses_baselines,
)
from romwiki.cli.extract import extract
from romwiki.cli.regenerate import (
    _cache_sharing_groups,
    _generate_prepared_sites,
    _generate_site_group_in_worker,
    _PreparedSite,
    _SiteGeneration,
    run_generation,
)
from romwiki.profiles.loader import ProfileRepository
from romwiki.sites import GameMetadata, SiteCatalog, SiteDefinition
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGamePaths
from tests.conftest import make_gba_header

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class MainErrorHandlingTests(unittest.TestCase):
    def test_a_rom_wiki_error_is_reported_and_exits_nonzero(self) -> None:
        with self.assertLogs("romwiki", level="ERROR") as logs:
            exit_code = main(["inspect", "--rom", "/no/such/rom.nds"])

        self.assertEqual(exit_code, 1)
        self.assertIn("ROM image does not exist", "\n".join(logs.output))

    def test_usage_errors_keep_the_argparse_exit_status(self) -> None:
        with (
            patch("sys.stderr"),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["inspect", "--no-such-option"])

        self.assertEqual(raised.exception.code, 2)

    def test_an_unknown_command_is_rejected_by_argparse(self) -> None:
        with self.assertRaises(SystemExit):
            main(["not-a-real-command"])

    def test_top_level_help_exposes_grouped_commands_only(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if getattr(action, "choices", None)
        )

        self.assertEqual(
            set(subparsers.choices),
            {
                "inspect",
                "extract",
                "build",
                "generate",
                "regenerate",
                "baseline",
                "site",
            },
        )

    def test_generate_all_is_catalog_driven(self) -> None:
        with patch("romwiki.cli.regenerate.run_generation") as generate:
            exit_code = main(["generate", "--all"])

        self.assertEqual(exit_code, 0)
        args = generate.call_args.args[0]
        self.assertTrue(args.regenerate_all)

    def test_site_group_exposes_data_and_frontend_commands(self) -> None:
        parser = build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        site_parser = subparsers.choices["site"]
        site_subparsers = next(
            action
            for action in site_parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

        self.assertEqual(
            set(site_subparsers.choices),
            {
                "list",
                "export-web",
                "snapshot-web",
                "restore-web",
                "pack-pokedb",
                "restore-pokedb",
                "bundle-generator",
            },
        )

    def test_version_family_parser_accepts_three_games_and_labels(self) -> None:
        args = build_parser().parse_args(
            [
                "build",
                "family",
                "--games",
                "red",
                "blue",
                "yellow",
                "--versions",
                "red-hack",
                "blue-hack",
                "yellow-hack",
                "--site-id",
                "test-family",
            ]
        )

        self.assertEqual(args.games, ["red", "blue", "yellow"])
        self.assertEqual(args.versions, ["red-hack", "blue-hack", "yellow-hack"])

    def test_regenerate_parser_exposes_complete_workflow_options(self) -> None:
        args = build_parser().parse_args(["regenerate", "--all", "--refresh"])

        self.assertTrue(args.regenerate_all)
        self.assertTrue(args.refresh)

    def test_parser_exposes_global_logging_options(self) -> None:
        verbose = build_parser().parse_args(["--verbose", "regenerate", "--all"])
        quiet = build_parser().parse_args(["--quiet", "regenerate", "--all"])

        self.assertTrue(verbose.verbose)
        self.assertFalse(verbose.quiet)
        self.assertTrue(quiet.quiet)
        self.assertFalse(quiet.verbose)

    def test_site_list_emits_published_json_for_automation(self) -> None:
        with patch("builtins.print") as output:
            exit_code = main(["site", "list", "--published", "--json"])

        self.assertEqual(exit_code, 0)
        sites = json.loads(output.call_args.args[0])
        self.assertEqual(
            [site["id"] for site in sites],
            [
                "portal",
                "firered-leafgreen",
                "firered-omega",
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
        self.assertEqual(sites[0]["kind"], "portal")
        self.assertEqual({site["kind"] for site in sites[1:]}, {"game"})

    def test_inspect_prints_json_for_a_matched_profile(self) -> None:
        rom_path = Path(".local/roms/Pokemon - Renegade Platinum.nds")
        if not rom_path.is_file():
            self.skipTest("local ROM fixture is not available in this environment")

        exit_code = main(["inspect", "--rom", str(rom_path), "--json"])

        self.assertEqual(exit_code, 0)

    def test_inspect_prints_text_for_an_unmatched_gba_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom_path = Path(directory) / "hack.gba"
            rom_path.write_bytes(
                make_gba_header(software_version=1).ljust(0x1000, b"\0")
            )
            with patch("builtins.print") as printed:
                exit_code = main(["inspect", "--rom", str(rom_path)])

        lines = [call.args[0] for call in printed.call_args_list]
        self.assertEqual(exit_code, 0)
        self.assertIn("ROM version: 1", lines)
        self.assertIn("Profile: unknown", lines)
        self.assertFalse(any(line.startswith("Files:") for line in lines))

    def test_dppt_location_extraction_uses_integrated_trade_records(self) -> None:
        profile = SimpleNamespace(
            id="platinum-us",
            engine="gen4_platinum",
            layout={"npc_trades": "trades.narc"},
            parameters={},
        )
        result = SimpleNamespace(match=SimpleNamespace(profile=profile))
        locations = {"game": profile.id, "record_count": 1, "records": [{}]}

        with (
            patch(
                "romwiki.cli.extract.extract_item_dataset",
                return_value={"records": []},
            ),
            patch("romwiki.cli.extract.extract_npc_trade_dataset") as extract_trades,
            patch(
                "romwiki.cli.extract.extract_location_dataset", return_value=locations
            ) as extract_locations,
            patch("romwiki.cli.extract.write_dataset"),
            patch("builtins.print"),
        ):
            extract("locations", result, Path("locations.json"))

        extract_trades.assert_not_called()
        self.assertIsNone(extract_locations.call_args.kwargs["trade_dataset"])


class VersionFamilyInputTests(unittest.TestCase):
    def test_defaults_version_labels_to_game_ids(self) -> None:
        self.assertEqual(
            version_family_inputs(["black", "white"], None),
            (("black", "white"), ("black", "white")),
        )

    def test_requires_at_least_two_games(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "at least two games"):
            version_family_inputs(["black"], None)

    def test_requires_one_label_per_game(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "one label"):
            version_family_inputs(["black", "white"], ["black"])

    def test_requires_unique_labels(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "must be unique"):
            version_family_inputs(["black", "white"], ["hack", "hack"])

    def test_detects_consistent_baseline_configuration(self) -> None:
        without_baselines = {
            "black": LocalGamePaths("black", Path("black.nds"), None),
            "white": LocalGamePaths("white", Path("white.nds"), None),
        }
        with_baselines = {
            "black": LocalGamePaths("black", Path("black.nds"), Path("base-black.nds")),
            "white": LocalGamePaths("white", Path("white.nds"), Path("base-white.nds")),
        }

        self.assertFalse(version_family_uses_baselines(without_baselines))
        self.assertTrue(version_family_uses_baselines(with_baselines))

    def test_derives_pokedb_generation_from_profiles(self) -> None:
        repository = ProfileRepository.load(REPOSITORY_ROOT / "profiles")
        profiles = {profile.id: profile for profile in repository.profiles}

        no_config = Path("missing/games.toml")
        self.assertEqual(
            resolve_pokedb_path(None, (profiles["platinum-us"],), no_config),
            Path("../pokedb/.output/gen4"),
        )
        self.assertEqual(
            resolve_pokedb_path(
                None,
                (profiles["black-us"], profiles["white-us"]),
                no_config,
            ),
            Path("../pokedb/.output/gen5"),
        )

    def test_local_configuration_selects_the_pokedb_root(self) -> None:
        repository = ProfileRepository.load(REPOSITORY_ROOT / "profiles")
        profile = next(
            profile for profile in repository.profiles if profile.id == "platinum-us"
        )
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "games.toml"
            config.write_text(
                'pokedb_root = "pokedb"\n'
                '[games.platinum-us]\npatched_rom = "platinum.nds"\n',
                encoding="utf-8",
            )

            self.assertEqual(
                resolve_pokedb_path(None, (profile,), config),
                (Path(directory) / "pokedb" / "gen4").resolve(),
            )
            self.assertEqual(
                resolve_pokedb_root(Path("custom/pokedb"), config),
                Path("custom/pokedb"),
            )

    def test_explicit_pokedb_path_overrides_profile_generation(self) -> None:
        repository = ProfileRepository.load(REPOSITORY_ROOT / "profiles")
        profile = next(
            profile for profile in repository.profiles if profile.id == "black-us"
        )

        self.assertEqual(
            resolve_pokedb_path(
                Path("custom/pokedb"), (profile,), Path("missing/games.toml")
            ),
            Path("custom/pokedb"),
        )

    def test_rejects_mixed_baseline_configuration(self) -> None:
        paths = {
            "black": LocalGamePaths("black", Path("black.nds"), Path("base-black.nds")),
            "white": LocalGamePaths("white", Path("white.nds"), None),
        }

        with self.assertRaisesRegex(LocalConfigError, "every game"):
            version_family_uses_baselines(paths)


class WikiOutputPathTests(unittest.TestCase):
    def test_resolves_profile_to_its_catalog_site(self) -> None:
        self.assertEqual(
            profile_wiki_root("platinum-us", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/platinum/wiki",
        )
        self.assertEqual(
            profile_wiki_root("renegade-platinum", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/renegade-platinum/wiki",
        )

    def test_unknown_profile_retains_the_conventional_fallback(self) -> None:
        self.assertEqual(
            profile_wiki_root("new-game", root=REPOSITORY_ROOT),
            Path("sites/games/new-game/wiki"),
        )

    def test_resolves_family_site_from_the_catalog(self) -> None:
        self.assertEqual(
            site_wiki_root("black-white", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/black-white/wiki",
        )


class CliInputResolutionTests(unittest.TestCase):
    def test_resolves_configured_game_and_base_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            base = root / "base.nds"
            patched.touch()
            base.touch()
            config = root / "games.toml"
            config.write_text(
                """
[games.test-game]
patched_rom = "patched.nds"
base_rom = "base.nds"
""".strip(),
                encoding="utf-8",
            )
            patched_args = build_parser().parse_args(
                ["inspect", "--game", "test-game", "--games-config", str(config)]
            )
            base_args = build_parser().parse_args(
                [
                    "inspect",
                    "--game",
                    "test-game",
                    "--base",
                    "--games-config",
                    str(config),
                ]
            )

            self.assertEqual(resolve_input_rom(patched_args), patched.resolve())
            self.assertEqual(resolve_input_rom(base_args), base.resolve())

    def test_resolves_explicit_rom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "explicit.nds"
            rom.touch()
            args = build_parser().parse_args(["inspect", "--rom", str(rom)])

            self.assertEqual(resolve_input_rom(args), rom.resolve())

    def test_configured_build_uses_base_rom_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            base = root / "base.nds"
            patched.touch()
            base.touch()
            config = root / "games.toml"
            config.write_text(
                "[games.test]\npatched_rom='patched.nds'\nbase_rom='base.nds'\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                ["build", "game", "--game", "test", "--games-config", str(config)]
            )

            self.assertEqual(resolve_build_baseline(args), base.resolve())

    def test_configured_build_reports_a_stale_base_rom_path_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patched = root / "patched.nds"
            patched.touch()
            config = root / "games.toml"
            config.write_text(
                "[games.test]\npatched_rom='patched.nds'\nbase_rom='missing-base.nds'\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                ["build", "game", "--game", "test", "--games-config", str(config)]
            )

            with self.assertRaisesRegex(LocalConfigError, "does not exist"):
                resolve_build_baseline(args)

    def test_configured_retail_build_without_base_is_standalone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rom = root / "retail.nds"
            rom.touch()
            config = root / "games.toml"
            config.write_text(
                "[games.retail]\npatched_rom='retail.nds'\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                [
                    "build",
                    "game",
                    "--game",
                    "retail",
                    "--games-config",
                    str(config),
                ]
            )

            self.assertIsNone(resolve_build_baseline(args))

    def test_explicit_build_requires_base_or_hack_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "hack.nds"
            rom.touch()
            args = build_parser().parse_args(["build", "moves", "--rom", str(rom)])
            hack_only = build_parser().parse_args(
                ["build", "moves", "--rom", str(rom), "--hack-only"]
            )

            with self.assertRaisesRegex(LocalConfigError, "require --base-rom"):
                resolve_build_baseline(args)
            self.assertIsNone(resolve_build_baseline(hack_only))

    def test_resolves_an_explicit_base_rom_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.nds"
            base.touch()
            args = build_parser().parse_args(
                ["build", "game", "--game", "test", "--base-rom", str(base)]
            )

            self.assertEqual(resolve_build_baseline(args), base.resolve())

    def test_rejects_a_missing_explicit_base_rom_path(self) -> None:
        args = build_parser().parse_args(
            ["build", "game", "--game", "test", "--base-rom", "missing-base.nds"]
        )

        with self.assertRaisesRegex(LocalConfigError, "does not exist"):
            resolve_build_baseline(args)

    def test_rejects_base_rom_combined_with_hack_only_or_base(self) -> None:
        hack_only_args = build_parser().parse_args(
            [
                "build",
                "game",
                "--game",
                "test",
                "--base-rom",
                "base.nds",
                "--hack-only",
            ]
        )
        base_args = build_parser().parse_args(
            [
                "build",
                "game",
                "--game",
                "test",
                "--base-rom",
                "base.nds",
                "--base",
            ]
        )

        for args in (hack_only_args, base_args):
            with self.assertRaisesRegex(
                LocalConfigError, "cannot be combined with --hack-only or --base"
            ):
                resolve_build_baseline(args)

    def test_comparative_build_without_game_or_base_rom_is_rejected(self) -> None:
        args = build_parser().parse_args(["build", "game"])

        with self.assertRaisesRegex(LocalConfigError, "require --game or --base-rom"):
            resolve_build_baseline(args)

    def test_missing_game_and_rom_is_rejected(self) -> None:
        args = build_parser().parse_args(["inspect"])

        with self.assertRaisesRegex(
            LocalConfigError, "Specify a ROM path or select a configured game"
        ):
            resolve_input_rom(args)


class RegenerationTests(unittest.TestCase):
    def test_dispatches_single_and_version_family_builds_from_site_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pokedb_root = root / "pokedb"
            (pokedb_root / "gen4").mkdir(parents=True)
            (pokedb_root / "gen5").mkdir()
            roms = root / "roms"
            roms.mkdir()
            for name in ("platinum-us", "black-us", "white-us"):
                (roms / f"{name}.nds").touch()
            games_config = root / "games.toml"
            games_config.write_text(
                """
[games.platinum-us]
patched_rom = "roms/platinum-us.nds"
[games.black-us]
patched_rom = "roms/black-us.nds"
[games.white-us]
patched_rom = "roms/white-us.nds"
""".strip(),
                encoding="utf-8",
            )
            sites = (
                _site(root, "portal", "portal", None),
                _site(
                    root,
                    "platinum",
                    "game",
                    _game(("platinum-us",), (), 4),
                ),
                _site(
                    root,
                    "black-white",
                    "game",
                    _game(("black-us", "white-us"), ("black", "white"), 4),
                ),
            )
            catalog = SiteCatalog(root, sites)
            args = SimpleNamespace(
                root=root,
                site_ids=[],
                regenerate_all=True,
                games_config=games_config,
                profiles_dir=root / "profiles",
                pokedb_root=pokedb_root,
                data_root=root / "data",
                refresh=True,
                jobs=1,
            )

            def inspection(
                path: Path,
                profiles_dir: Path,
                *,
                profiles: object,
            ) -> SimpleNamespace:
                del profiles_dir, profiles
                profile_id = path.stem
                return SimpleNamespace(
                    match=SimpleNamespace(profile=SimpleNamespace(id=profile_id))
                )

            with (
                patch("romwiki.cli.regenerate.SiteCatalog.load", return_value=catalog),
                patch(
                    "romwiki.cli.regenerate.regeneration_profiles",
                    return_value=object(),
                ),
                patch(
                    "romwiki.cli.regenerate.PokeDBGeneration.load",
                    return_value=object(),
                ) as load_pokedb,
                patch(
                    "romwiki.cli.regenerate.inspect_rom",
                    side_effect=inspection,
                ) as inspect,
                patch(
                    "romwiki.cli.regenerate.GameBuildWorkflow",
                    side_effect=lambda result, *args, **kwargs: result,
                ) as workflow,
                patch("romwiki.cli.regenerate.write_game_build") as build_game,
                patch(
                    "romwiki.cli.regenerate.write_version_family_build"
                ) as build_family,
                patch(
                    "romwiki.cli.regenerate.regeneration_fingerprint",
                    return_value="fingerprint",
                ),
                patch(
                    "romwiki.cli.regenerate.can_reuse_generation", return_value=False
                ),
                patch("romwiki.cli.regenerate.write_regeneration_state"),
                self.assertLogs("romwiki", level="INFO") as logs,
            ):
                run_generation(args)

            self.assertEqual(inspect.call_count, 3)
            self.assertEqual(load_pokedb.call_count, 1)
            self.assertEqual(
                build_game.call_args.args[0].match.profile.id, "platinum-us"
            )
            self.assertEqual(
                build_game.call_args.kwargs,
                {
                    "data_root": root / "data" / "platinum-us",
                    "wiki_root": root / "sites" / "platinum" / "wiki",
                },
            )
            self.assertEqual(
                [call.kwargs["baseline"] for call in workflow.call_args_list],
                [None, None, None],
            )
            self.assertTrue(
                all(call.kwargs["refresh_current"] for call in workflow.call_args_list)
            )
            site_id, workflows, versions = build_family.call_args.args
            self.assertEqual(site_id, "black-white")
            self.assertEqual(versions, ("black", "white"))
            self.assertEqual(
                {
                    version: result.match.profile.id
                    for version, result in workflows.items()
                },
                {"black": "black-us", "white": "white-us"},
            )
            self.assertEqual(
                build_family.call_args.kwargs,
                {
                    "data_root": root / "data" / "black-white",
                    "wiki_root": root / "sites" / "black-white" / "wiki",
                },
            )
            messages = "\n".join(logs.output)
            self.assertIn("Generation preflight [1/2]: platinum", messages)
            self.assertIn("Generation preflight [2/2]: black-white", messages)
            self.assertIn("Generation [1/2] platinum: checking inputs", messages)
            self.assertIn("Generation [2/2] black-white: checking inputs", messages)
            self.assertIn("Catalog generation completed in", messages)

    def test_sites_sharing_an_extraction_cache_are_generated_together(
        self,
    ) -> None:
        def generation(site_id: str, current: str, base: str | None) -> object:
            return _site_generation(site_id, (current,), (base,))

        retail = generation("platinum", "platinum-us", None)
        hack = generation("renegade-platinum", "renegade-platinum", "platinum-us")
        other = generation("emerald", "emerald-us", None)
        sibling = _site_generation(
            "blaze-black-2-volt-white-2",
            ("blaze-black-2", "volt-white-2"),
            ("black-2-us", "white-2-us"),
        )
        redux = _site_generation(
            "redux",
            ("blaze-black-2-redux", "volt-white-2-redux"),
            ("black-2-us", "white-2-us"),
        )

        groups = _cache_sharing_groups([retail, hack, sibling, other, redux])

        self.assertEqual(
            [[item.prepared.site.id for item in group] for group in groups],
            [
                ["platinum"],
                ["renegade-platinum"],
                ["blaze-black-2-volt-white-2", "redux"],
                ["emerald"],
            ],
        )

    def test_parallel_generation_reports_failures_after_every_site_settles(
        self,
    ) -> None:
        generations = [
            _site_generation("first", ("first-us",), (None,)),
            _site_generation("second", ("second-us",), (None,)),
        ]
        attempted = []

        def generate_group(group: tuple, options: object, log_level: int) -> None:
            del options, log_level
            attempted.append(group[0].prepared.site.id)
            if group[0].prepared.site.id == "first":
                raise SiteError("first failed")

        args = SimpleNamespace(
            root=Path("."),
            pokedb_root=Path("pokedb"),
            data_root=Path("data"),
            refresh=False,
            clean=True,
            jobs=2,
        )
        with (
            patch(
                "romwiki.cli.regenerate.regeneration_fingerprint",
                return_value="fingerprint",
            ),
            patch("romwiki.cli.regenerate.ProcessPoolExecutor", ThreadPoolExecutor),
            patch(
                "romwiki.cli.regenerate._generate_site_group_in_worker",
                side_effect=generate_group,
            ),
            patch("romwiki.cli.regenerate.LOG"),
            self.assertRaisesRegex(SiteError, "first failed"),
        ):
            _generate_prepared_sites(
                args,
                [generation.prepared for generation in generations],
            )

        self.assertEqual(sorted(attempted), ["first", "second"])

    def test_generation_worker_names_the_failed_site(self) -> None:
        generation = _site_generation("broken", ("broken-us",), (None,))

        with (
            patch("romwiki.cli.regenerate.logging.basicConfig") as configure,
            patch(
                "romwiki.cli.regenerate._generate_site",
                side_effect=LocalConfigError("missing input"),
            ),
            self.assertLogs("romwiki", level="ERROR") as logs,
            self.assertRaisesRegex(LocalConfigError, "missing input"),
        ):
            _generate_site_group_in_worker((generation,), object(), 20)

        self.assertIn("[broken]", configure.call_args.kwargs["format"])
        self.assertIn("broken failed: missing input", "\n".join(logs.output))

    def test_generation_rejects_non_positive_job_counts(self) -> None:
        args = SimpleNamespace(data_root=Path("data"), refresh=False, jobs=0)

        with self.assertRaisesRegex(SiteError, "at least 1"):
            _generate_prepared_sites(args, [])


def _site_generation(
    site_id: str,
    current: tuple[str, ...],
    baselines: tuple[str | None, ...],
) -> _SiteGeneration:
    def inspection(profile_id: str | None) -> Any:
        if profile_id is None:
            return None
        return SimpleNamespace(
            match=SimpleNamespace(profile=SimpleNamespace(id=profile_id))
        )

    site = _site(Path("root"), site_id, "game", _game(current, (), 4))
    prepared = _PreparedSite(
        site,
        tuple(inspection(profile_id) for profile_id in current),
        tuple(inspection(profile_id) for profile_id in baselines),
        Path("pokedb/gen4"),
    )
    return _SiteGeneration(prepared, "1/1", Path(f"{site_id}.json"), "fingerprint")


def _game(
    profiles: tuple[str, ...],
    versions: tuple[str, ...],
    generation: int,
) -> GameMetadata:
    return GameMetadata(
        profiles=profiles,
        versions=versions,
        generation=generation,
        base_game="test",
        platform="nintendo-ds",
        platform_name="Nintendo DS",
        creator="Test",
    )


def _site(
    root: Path,
    site_id: str,
    kind: str,
    game: GameMetadata | None,
) -> SiteDefinition:
    return SiteDefinition(
        id=site_id,
        name=site_id,
        kind=kind,
        slug="" if kind == "portal" else site_id,
        published=True,
        order=0,
        config_path=root / "sites" / site_id / "game.toml",
        description="",
        theme="portal" if kind == "portal" else "platinum",
        game=game,
    )


if __name__ == "__main__":
    unittest.main()
