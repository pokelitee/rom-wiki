from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.cli import (
    _comparison_workflow_kind,
    _current_relationship_datasets,
    _dataset_output,
    _load_comparisons,
    _profile_wiki_root,
    _report_site_audit,
    _resolve_build_baseline,
    _resolve_input_rom,
    _resolve_pokedb_path,
    _run_full_game_build,
    _run_regeneration,
    _run_rom_command,
    _run_section_build,
    _run_version_family_build,
    _site_wiki_root,
    _version_family_inputs,
    _version_family_uses_baselines,
    build_parser,
    main,
)
from romwiki.profiles.loader import ProfileRepository
from romwiki.sites import (
    GameMetadata,
    SiteAuditIssue,
    SiteAuditReport,
    SiteCatalog,
    SiteDefinition,
)
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGamePaths

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class MainErrorHandlingTests(unittest.TestCase):
    def test_a_rom_wiki_error_is_reported_and_exits_nonzero(self) -> None:
        exit_code = main(["inspect", "--rom", "/no/such/rom.nds"])

        self.assertEqual(exit_code, 2)

    def test_combined_dev_server_arguments_are_forwarded(self) -> None:
        catalog = object()
        with (
            patch("romwiki.cli.SiteCatalog.load", return_value=catalog),
            patch("romwiki.cli.serve_sites") as serve,
        ):
            exit_code = main(
                [
                    "site",
                    "serve",
                    "--all",
                    "--dev",
                    "--output",
                    "build/preview",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "9000",
                ]
            )

        self.assertEqual(exit_code, 0)
        serve.assert_called_once_with(
            catalog,
            Path("build/preview"),
            site_ids=[],
            serve_all=True,
            dev=True,
            host="0.0.0.0",
            port=9000,
        )

    def test_individual_dev_server_arguments_are_forwarded(self) -> None:
        catalog = object()
        with (
            patch("romwiki.cli.SiteCatalog.load", return_value=catalog),
            patch("romwiki.cli.serve_sites") as serve,
        ):
            exit_code = main(["site", "serve", "renegade-platinum", "--dev"])

        self.assertEqual(exit_code, 0)
        serve.assert_called_once_with(
            catalog,
            Path("build/mkdocs-dev"),
            site_ids=["renegade-platinum"],
            serve_all=False,
            dev=True,
            host="127.0.0.1",
            port=8000,
        )

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

    def test_generate_all_dev_is_catalog_driven(self) -> None:
        with patch("romwiki.cli._run_generation") as generate:
            exit_code = main(["generate", "--all", "--dev"])

        self.assertEqual(exit_code, 0)
        args = generate.call_args.args[0]
        self.assertTrue(args.regenerate_all)
        self.assertTrue(args.dev)

    def test_dev_site_build_uses_the_dev_default_output(self) -> None:
        catalog = object()
        built = SimpleNamespace(
            id="platinum",
            output_path=lambda output: output / "platinum",
        )
        with (
            patch("romwiki.cli.SiteCatalog.load", return_value=catalog),
            patch("romwiki.cli.build_sites", return_value=(built,)) as build,
        ):
            exit_code = main(["site", "build", "--all", "--dev"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(build.call_args.args[1], Path("build/mkdocs-dev"))
        self.assertTrue(build.call_args.kwargs["dev"])

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
        args = build_parser().parse_args(
            ["regenerate", "--all", "--refresh", "--snapshot"]
        )

        self.assertTrue(args.regenerate_all)
        self.assertTrue(args.refresh)
        self.assertTrue(args.snapshot)

        incremental = build_parser().parse_args(
            ["regenerate", "heart-gold-soul-silver", "--incremental"]
        )
        self.assertTrue(incremental.incremental)

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
        self.assertFalse(sites[0]["data_driven"])
        self.assertTrue(sites[1]["data_driven"])
        self.assertTrue(sites[4]["data_driven"])

    def test_inspect_prints_json_for_a_matched_profile(self) -> None:
        rom_path = Path(".local/roms/Pokemon - Renegade Platinum.nds")
        if not rom_path.is_file():
            self.skipTest("local ROM fixture is not available in this environment")

        exit_code = main(["inspect", "--rom", str(rom_path), "--json"])

        self.assertEqual(exit_code, 0)

    def test_dppt_location_extraction_uses_integrated_trade_records(self) -> None:
        profile = SimpleNamespace(
            id="platinum-us",
            engine="gen4_dppt",
            layout={"npc_trades": "trades.narc"},
            parameters={},
        )
        result = SimpleNamespace(match=SimpleNamespace(profile=profile))
        args = SimpleNamespace(
            command="extract-locations", output=Path("locations.json")
        )
        locations = {"game": profile.id, "record_count": 1, "records": [{}]}

        with (
            patch("romwiki.cli.extract_item_dataset", return_value={"records": []}),
            patch("romwiki.cli.extract_npc_trade_dataset") as extract_trades,
            patch(
                "romwiki.cli.extract_location_dataset", return_value=locations
            ) as extract_locations,
            patch("romwiki.cli.write_dataset"),
            patch("builtins.print"),
        ):
            _run_rom_command(args, result)

        extract_trades.assert_not_called()
        self.assertIsNone(extract_locations.call_args.kwargs["trade_dataset"])


class VersionFamilyInputTests(unittest.TestCase):
    def test_defaults_version_labels_to_game_ids(self) -> None:
        self.assertEqual(
            _version_family_inputs(["black", "white"], None),
            (("black", "white"), ("black", "white")),
        )

    def test_requires_at_least_two_games(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "at least two games"):
            _version_family_inputs(["black"], None)

    def test_requires_one_label_per_game(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "one label"):
            _version_family_inputs(["black", "white"], ["black"])

    def test_requires_unique_labels(self) -> None:
        with self.assertRaisesRegex(LocalConfigError, "must be unique"):
            _version_family_inputs(["black", "white"], ["hack", "hack"])

    def test_detects_consistent_baseline_configuration(self) -> None:
        without_baselines = {
            "black": LocalGamePaths("black", Path("black.nds"), None),
            "white": LocalGamePaths("white", Path("white.nds"), None),
        }
        with_baselines = {
            "black": LocalGamePaths("black", Path("black.nds"), Path("base-black.nds")),
            "white": LocalGamePaths("white", Path("white.nds"), Path("base-white.nds")),
        }

        self.assertFalse(_version_family_uses_baselines(without_baselines))
        self.assertTrue(_version_family_uses_baselines(with_baselines))

    def test_derives_pokedb_generation_from_profiles(self) -> None:
        repository = ProfileRepository.load(REPOSITORY_ROOT / "profiles")
        profiles = {profile.id: profile for profile in repository.profiles}

        self.assertEqual(
            _resolve_pokedb_path(None, (profiles["platinum-us"],)),
            Path("../pokedb/.output/gen4"),
        )
        self.assertEqual(
            _resolve_pokedb_path(
                None,
                (profiles["black-us"], profiles["white-us"]),
            ),
            Path("../pokedb/.output/gen5"),
        )

    def test_explicit_pokedb_path_overrides_profile_generation(self) -> None:
        repository = ProfileRepository.load(REPOSITORY_ROOT / "profiles")
        profile = next(
            profile for profile in repository.profiles if profile.id == "black-us"
        )

        self.assertEqual(
            _resolve_pokedb_path(Path("custom/pokedb"), (profile,)),
            Path("custom/pokedb"),
        )

    def test_rejects_mixed_baseline_configuration(self) -> None:
        paths = {
            "black": LocalGamePaths("black", Path("black.nds"), Path("base-black.nds")),
            "white": LocalGamePaths("white", Path("white.nds"), None),
        }

        with self.assertRaisesRegex(LocalConfigError, "every game"):
            _version_family_uses_baselines(paths)


class DatasetOutputPathTests(unittest.TestCase):
    def test_locations_use_the_raw_filename(self) -> None:
        self.assertEqual(
            _dataset_output(Path("build/data/game"), "locations"),
            Path("build/data/game/locations/raw.json"),
        )

    def test_every_other_kind_uses_the_enriched_filename(self) -> None:
        for kind in (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "trainers",
        ):
            self.assertEqual(
                _dataset_output(Path("build/data/game"), kind),
                Path(f"build/data/game/{kind}/enriched.json"),
            )


class WikiOutputPathTests(unittest.TestCase):
    def test_resolves_profile_to_its_catalog_site(self) -> None:
        self.assertEqual(
            _profile_wiki_root("platinum-us", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/platinum/wiki",
        )
        self.assertEqual(
            _profile_wiki_root("renegade-platinum", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/renegade-platinum/wiki",
        )

    def test_unknown_profile_retains_the_conventional_fallback(self) -> None:
        self.assertEqual(
            _profile_wiki_root("new-game", root=REPOSITORY_ROOT),
            Path("sites/games/new-game/wiki"),
        )

    def test_resolves_family_site_from_the_catalog(self) -> None:
        self.assertEqual(
            _site_wiki_root("black-white", root=REPOSITORY_ROOT),
            REPOSITORY_ROOT / "sites/games/black-white/wiki",
        )


class FocusedSectionBuildTests(unittest.TestCase):
    def test_encounter_build_includes_location_relationships(self) -> None:
        encounters = {
            "game": "test",
            "records": [
                {
                    "area_id": 8,
                    "map_index": 3,
                    "season": "spring",
                    "name": "Route 1",
                }
            ],
        }
        locations = {
            "game": "test",
            "records": [
                {
                    "header_id": 6,
                    "name": "Route 1",
                    "encounter_map_index": 3,
                }
            ],
        }
        pokemon = {"game": "test", "records": []}
        current = SimpleNamespace(
            profile=SimpleNamespace(id="test"),
            encounters=lambda: encounters,
            locations=lambda: locations,
            pokemon=lambda: pokemon,
        )
        workflow = SimpleNamespace(
            current=current,
            build=lambda kind: SimpleNamespace(
                current=encounters,
                comparison=None,
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(
                command="build-encounters",
                dev=False,
                wiki_output=root / "wiki" / "encounters",
                data_output=root / "data" / "encounters" / "enriched.json",
            )
            with (
                patch("romwiki.cli._create_build_workflow", return_value=workflow),
                patch("romwiki.cli._write_dataset_build") as write_build,
                patch("romwiki.cli.render_changes_pages"),
            ):
                _run_section_build(args, SimpleNamespace())

        relationships = write_build.call_args.kwargs["relationship_index"]
        self.assertEqual(
            relationships.encounter_locations["map-003"][0].header_id,
            6,
        )
        self.assertIsNotNone(write_build.call_args.kwargs["reference_index"])


class RelationshipDatasetTests(unittest.TestCase):
    def test_collects_companions_and_omits_unsupported_datasets(self) -> None:
        datasets = {
            kind: {"game": "test", "records": []}
            for kind in ("pokemon", "encounters", "items")
        }
        context = SimpleNamespace(
            pokemon=lambda: datasets["pokemon"],
            encounters=lambda: datasets["encounters"],
            trainers=lambda: None,
            locations=lambda: None,
            items=lambda: datasets["items"],
            trades=lambda: None,
        )

        self.assertEqual(_current_relationship_datasets(context), datasets)


class OptionalSectionBuildTests(unittest.TestCase):
    def test_full_game_build_writes_only_enabled_datasets(self) -> None:
        kinds = ("pokemon", "abilities", "moves", "items", "encounters")
        builds = {
            kind: SimpleNamespace(
                current=_build_dataset(kind, "partial"),
                comparison=None,
            )
            for kind in kinds
        }
        current = SimpleNamespace(
            profile=SimpleNamespace(id="partial"),
            trades=lambda: None,
        )
        workflow = SimpleNamespace(current=current, build_all=lambda: builds)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(
                data_root=root / "data",
                wiki_root=root / "wiki",
                dev=False,
            )
            with (
                patch(
                    "romwiki.cli.build_type_dataset",
                    return_value=_build_dataset("types", "partial"),
                ),
                patch("romwiki.cli._write_type_build"),
                patch("romwiki.cli._write_dataset_build") as write_dataset,
                patch("romwiki.cli.render_changes_pages", return_value=0),
            ):
                _run_full_game_build(args, SimpleNamespace(), workflow=workflow)

        self.assertEqual(
            [call.args[0] for call in write_dataset.call_args_list],
            list(kinds),
        )

    def test_version_family_rejects_mismatched_optional_sections(self) -> None:
        partial = _section_profile("partial")
        complete = _section_profile("complete", optional=True)
        workflows = {
            "one": SimpleNamespace(current=SimpleNamespace(profile=partial)),
            "two": SimpleNamespace(current=SimpleNamespace(profile=complete)),
        }
        args = SimpleNamespace(
            site_id="test-family",
            games=["partial", "complete"],
            versions=["one", "two"],
        )

        with self.assertRaisesRegex(
            LocalConfigError,
            "different dataset sections.*one omits locations, trainers",
        ):
            _run_version_family_build(args, workflows=workflows)


class ComparisonWorkflowKindTests(unittest.TestCase):
    def test_wild_encounters_maps_to_the_encounters_workflow_key(self) -> None:
        self.assertEqual(_comparison_workflow_kind("wild_encounters"), "encounters")

    def test_every_other_kind_passes_through_unchanged(self) -> None:
        for kind in ("pokemon", "abilities", "moves", "items", "trainers", "locations"):
            self.assertEqual(_comparison_workflow_kind(kind), kind)


class LoadComparisonsTests(unittest.TestCase):
    def test_missing_directory_yields_no_comparisons(self) -> None:
        self.assertEqual(_load_comparisons(Path("/no/such/comparisons/dir")), {})

    def test_reads_and_reindexes_comparison_files_by_workflow_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wild_encounters.json").write_text(
                json.dumps({"kind": "wild_encounters", "counts": {}}),
                encoding="utf-8",
            )
            (root / "pokemon.json").write_text(
                json.dumps({"kind": "pokemon", "counts": {}}),
                encoding="utf-8",
            )

            comparisons = _load_comparisons(root)

        self.assertEqual(set(comparisons), {"encounters", "pokemon"})
        self.assertEqual(comparisons["encounters"]["kind"], "wild_encounters")

    def test_ignores_malformed_or_non_comparison_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text("not json", encoding="utf-8")
            (root / "unrelated.json").write_text(
                json.dumps([1, 2, 3]), encoding="utf-8"
            )

            comparisons = _load_comparisons(root)

        self.assertEqual(comparisons, {})


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

            self.assertEqual(_resolve_input_rom(patched_args), patched.resolve())
            self.assertEqual(_resolve_input_rom(base_args), base.resolve())

    def test_resolves_explicit_rom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "explicit.nds"
            rom.touch()
            args = build_parser().parse_args(["inspect", "--rom", str(rom)])

            self.assertEqual(_resolve_input_rom(args), rom.resolve())

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

            self.assertEqual(_resolve_build_baseline(args), base.resolve())

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
                _resolve_build_baseline(args)

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

            self.assertIsNone(_resolve_build_baseline(args))

    def test_explicit_build_requires_base_or_hack_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "hack.nds"
            rom.touch()
            args = build_parser().parse_args(["build", "moves", "--rom", str(rom)])
            hack_only = build_parser().parse_args(
                ["build", "moves", "--rom", str(rom), "--hack-only"]
            )

            with self.assertRaisesRegex(LocalConfigError, "require --base-rom"):
                _resolve_build_baseline(args)
            self.assertIsNone(_resolve_build_baseline(hack_only))

    def test_resolves_an_explicit_base_rom_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.nds"
            base.touch()
            args = build_parser().parse_args(
                ["build", "game", "--game", "test", "--base-rom", str(base)]
            )

            self.assertEqual(_resolve_build_baseline(args), base.resolve())

    def test_rejects_a_missing_explicit_base_rom_path(self) -> None:
        args = build_parser().parse_args(
            ["build", "game", "--game", "test", "--base-rom", "missing-base.nds"]
        )

        with self.assertRaisesRegex(LocalConfigError, "does not exist"):
            _resolve_build_baseline(args)

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
                _resolve_build_baseline(args)

    def test_comparative_build_without_game_or_base_rom_is_rejected(self) -> None:
        args = build_parser().parse_args(["build", "game"])

        with self.assertRaisesRegex(LocalConfigError, "require --game or --base-rom"):
            _resolve_build_baseline(args)

    def test_missing_game_and_rom_is_rejected(self) -> None:
        args = build_parser().parse_args(["inspect"])

        with self.assertRaisesRegex(
            LocalConfigError, "Specify a ROM path or select a configured game"
        ):
            _resolve_input_rom(args)


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
                output=root / "dist",
                refresh=True,
                dev=True,
                snapshot=False,
                snapshot_output=root / "snapshot.tar.gz",
                max_page_kb=512,
                max_images=150,
                base_url=None,
                jobs=None,
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

            report = SiteAuditReport(3, 10, 100, ("index.html", 50), (), ())
            with (
                patch("romwiki.cli.SiteCatalog.load", return_value=catalog),
                patch("romwiki.cli._regeneration_profiles", return_value=object()),
                patch(
                    "romwiki.cli.PokeDBGeneration.load",
                    return_value=object(),
                ) as load_pokedb,
                patch(
                    "romwiki.cli.inspect_rom",
                    side_effect=inspection,
                ) as inspect,
                patch("romwiki.cli._run_full_game_build") as build_game,
                patch("romwiki.cli._run_version_family_build") as build_family,
                patch(
                    "romwiki.cli.regeneration_fingerprint",
                    return_value="fingerprint",
                ) as fingerprint,
                patch("romwiki.cli.can_reuse_generation", return_value=False),
                patch("romwiki.cli.write_regeneration_state"),
                patch(
                    "romwiki.cli.build_sites",
                    return_value=catalog.published(),
                ) as build_all_sites,
                patch(
                    "romwiki.cli.combined_artifact_files",
                    return_value={"index.html"},
                ),
                patch("romwiki.cli.audit_site", return_value=report) as audit,
                self.assertLogs("romwiki", level="INFO") as logs,
            ):
                _run_regeneration(args)

            self.assertEqual(inspect.call_count, 3)
            self.assertEqual(load_pokedb.call_count, 1)
            single_args = build_game.call_args.args[0]
            self.assertEqual(single_args.game, "platinum-us")
            self.assertEqual(
                single_args.wiki_root,
                root / "sites" / "platinum" / "wiki",
            )
            self.assertTrue(single_args.hack_only)
            self.assertTrue(single_args.dev)
            family_args = build_family.call_args.args[0]
            self.assertEqual(family_args.games, ["black-us", "white-us"])
            self.assertEqual(family_args.versions, ["black", "white"])
            self.assertEqual(family_args.site_id, "black-white")
            self.assertTrue(family_args.refresh_cache)
            self.assertTrue(family_args.dev)
            self.assertEqual(
                set(build_family.call_args.kwargs["workflows"]),
                {"black", "white"},
            )
            self.assertTrue(fingerprint.call_args.kwargs["dev"])
            self.assertTrue(build_all_sites.call_args.kwargs["dev"])
            self.assertTrue(audit.call_args.kwargs["ignore_missing_links"])
            messages = "\n".join(logs.output)
            self.assertIn("Generation preflight [1/2]: platinum", messages)
            self.assertIn("Generation preflight [2/2]: black-white", messages)
            self.assertIn("Generation [1/2] platinum: checking inputs", messages)
            self.assertIn("Generation [2/2] black-white: checking inputs", messages)
            self.assertIn("Complete regeneration completed in", messages)

    def test_snapshot_requires_complete_regeneration(self) -> None:
        args = SimpleNamespace(
            snapshot=True,
            regenerate_all=False,
        )

        with self.assertRaisesRegex(SiteError, "--snapshot requires --all"):
            _run_regeneration(args)

    def test_snapshot_rejects_incremental_builds(self) -> None:
        args = SimpleNamespace(
            snapshot=True,
            regenerate_all=True,
            incremental=True,
        )

        with self.assertRaisesRegex(SiteError, "cannot be combined"):
            _run_regeneration(args)

    def test_snapshot_rejects_development_regeneration(self) -> None:
        args = SimpleNamespace(
            snapshot=True,
            regenerate_all=True,
            incremental=False,
            dev=True,
        )

        with self.assertRaisesRegex(SiteError, "cannot be combined with --dev"):
            _run_regeneration(args)

    def test_site_audit_warnings_are_summarized_by_default(self) -> None:
        report = SiteAuditReport(
            1,
            2,
            100,
            ("index.html", 100),
            (),
            (
                SiteAuditIssue("image-count", "one.html", "too many"),
                SiteAuditIssue("image-count", "two.html", "too many"),
                SiteAuditIssue("css-unused", "assets", "unused"),
            ),
        )

        with self.assertLogs("romwiki", level="WARNING") as captured:
            _report_site_audit(report)

        output = "\n".join(captured.output)
        self.assertIn("3 warning(s)", output)
        self.assertIn("css-unused=1", output)
        self.assertIn("image-count=2", output)
        self.assertNotIn("one.html", output)


def _build_dataset(kind: str, game: str) -> dict:
    return {
        "schema_version": 1,
        "dataset": "wild_encounters" if kind == "encounters" else kind,
        "game": game,
        "source": {"rom_sha256": game},
        "records": [],
    }


def _section_profile(profile_id: str, *, optional: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=profile_id,
        layout={
            "personal": "personal",
            "messages": "messages",
            "moves": "moves",
            "item_data": "items",
            "encounters": "encounters",
            **(
                {
                    "trainer_data": "trainers",
                    "trainer_parties": "parties",
                    "map_headers": "headers",
                }
                if optional
                else {}
            ),
        },
    )


def _game(
    profiles: tuple[str, ...],
    versions: tuple[str, ...],
    generation: int,
) -> GameMetadata:
    return GameMetadata(
        profiles=profiles,
        versions=versions,
        data_driven=True,
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
        config_path=root / "sites" / site_id / "mkdocs.yml",
        description="",
        theme="portal" if kind == "portal" else "platinum",
        game=game,
    )


if __name__ == "__main__":
    unittest.main()
