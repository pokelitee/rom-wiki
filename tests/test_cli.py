from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from romwiki.cli import (
    _comparison_workflow_kind,
    _dataset_output,
    _load_comparisons,
    _resolve_build_baseline,
    _resolve_input_rom,
    _version_family_inputs,
    _version_family_uses_baselines,
    build_parser,
    main,
)
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGamePaths


class MainErrorHandlingTests(unittest.TestCase):
    def test_a_rom_wiki_error_is_reported_and_exits_nonzero(self) -> None:
        exit_code = main(["inspect", "/no/such/rom.nds"])

        self.assertEqual(exit_code, 2)

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


if __name__ == "__main__":
    unittest.main()
