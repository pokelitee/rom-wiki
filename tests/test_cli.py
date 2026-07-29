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
    _report_site_audit,
    _resolve_build_baseline,
    _resolve_input_rom,
    _run_regeneration,
    _version_family_inputs,
    _version_family_uses_baselines,
    build_parser,
    main,
)
from romwiki.sites import (
    GameMetadata,
    SiteAuditIssue,
    SiteAuditReport,
    SiteCatalog,
    SiteDefinition,
)
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGamePaths


class MainErrorHandlingTests(unittest.TestCase):
    def test_a_rom_wiki_error_is_reported_and_exits_nonzero(self) -> None:
        exit_code = main(["inspect", "/no/such/rom.nds"])

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

    def test_version_family_parser_accepts_three_games_and_labels(self) -> None:
        args = build_parser().parse_args(
            [
                "build-version-pair",
                "--games",
                "red",
                "blue",
                "yellow",
                "--versions",
                "red-hack",
                "blue-hack",
                "yellow-hack",
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
                "blaze-black-volt-white",
                "blaze-black-2-volt-white-2",
                "black-white",
            ],
        )
        self.assertFalse(sites[0]["data_driven"])
        self.assertTrue(sites[1]["data_driven"])
        self.assertFalse(sites[4]["data_driven"])

    def test_inspect_prints_json_for_a_matched_profile(self) -> None:
        rom_path = Path(".local/roms/Pokemon - Renegade Platinum.nds")
        if not rom_path.is_file():
            self.skipTest("local ROM fixture is not available in this environment")

        exit_code = main(["inspect", str(rom_path), "--json"])

        self.assertEqual(exit_code, 0)


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

    def test_preserves_positional_input_and_supports_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "explicit.nds"
            rom.touch()
            positional = build_parser().parse_args(["inspect", str(rom)])
            optional = build_parser().parse_args(["inspect", "--rom", str(rom)])

            self.assertEqual(_resolve_input_rom(positional), rom.resolve())
            self.assertEqual(_resolve_input_rom(optional), rom.resolve())

    def test_rejects_conflicting_explicit_inputs(self) -> None:
        args = build_parser().parse_args(
            ["inspect", "positional.nds", "--rom", "override.nds"]
        )

        with self.assertRaisesRegex(LocalConfigError, "not both"):
            _resolve_input_rom(args)

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
                ["build-game", "--game", "test", "--games-config", str(config)]
            )

            self.assertEqual(_resolve_build_baseline(args), base.resolve())

    def test_explicit_build_requires_base_or_hack_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "hack.nds"
            rom.touch()
            args = build_parser().parse_args(["build-moves", str(rom)])
            hack_only = build_parser().parse_args(
                ["build-moves", str(rom), "--hack-only"]
            )

            with self.assertRaisesRegex(LocalConfigError, "require --base-rom"):
                _resolve_build_baseline(args)
            self.assertIsNone(_resolve_build_baseline(hack_only))

    def test_resolves_an_explicit_base_rom_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.nds"
            base.touch()
            args = build_parser().parse_args(
                ["build-game", "--game", "test", "--base-rom", str(base)]
            )

            self.assertEqual(_resolve_build_baseline(args), base.resolve())

    def test_rejects_a_missing_explicit_base_rom_path(self) -> None:
        args = build_parser().parse_args(
            ["build-game", "--game", "test", "--base-rom", "missing-base.nds"]
        )

        with self.assertRaisesRegex(LocalConfigError, "does not exist"):
            _resolve_build_baseline(args)

    def test_rejects_base_rom_combined_with_hack_only_or_base(self) -> None:
        hack_only_args = build_parser().parse_args(
            ["build-game", "--game", "test", "--base-rom", "base.nds", "--hack-only"]
        )
        base_args = build_parser().parse_args(
            ["build-game", "--game", "test", "--base-rom", "base.nds", "--base"]
        )

        for args in (hack_only_args, base_args):
            with self.assertRaisesRegex(
                LocalConfigError, "cannot be combined with --hack-only or --base"
            ):
                _resolve_build_baseline(args)

    def test_comparative_build_without_game_or_base_rom_is_rejected(self) -> None:
        args = build_parser().parse_args(["build-game"])

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
                snapshot=False,
                snapshot_output=root / "snapshot.tar.gz",
                max_page_kb=512,
                max_images=150,
                base_url=None,
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
                patch("romwiki.cli._run_version_pair_build") as build_family,
                patch(
                    "romwiki.cli.build_sites",
                    return_value=catalog.published(),
                ),
                patch("romwiki.cli.audit_site", return_value=report),
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
            family_args = build_family.call_args.args[0]
            self.assertEqual(family_args.games, ["black-us", "white-us"])
            self.assertEqual(family_args.versions, ["black", "white"])
            self.assertEqual(family_args.site_id, "black-white")
            self.assertTrue(family_args.refresh_cache)
            self.assertEqual(
                set(build_family.call_args.kwargs["workflows"]),
                {"black", "white"},
            )

    def test_snapshot_requires_complete_regeneration(self) -> None:
        args = SimpleNamespace(
            snapshot=True,
            regenerate_all=False,
        )

        with self.assertRaisesRegex(SiteError, "--snapshot requires --all"):
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
