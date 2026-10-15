"""`romwiki build`: build one section, game, or sibling-version family."""

from __future__ import annotations

import argparse
from pathlib import Path

from romwiki.cli.common import (
    DEFAULT_DATA_ROOT,
    LOG,
    SubParsers,
    add_cache_argument,
    add_comparison_arguments,
    add_input_arguments,
    inspect_input,
    profile_wiki_root,
    resolve_pokedb_path,
    site_wiki_root,
    version_family_inputs,
    version_family_uses_baselines,
)
from romwiki.pipeline.build.outputs import (
    write_game_build,
    write_section_build,
    write_version_family_build,
)
from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry
from romwiki.util.logging import timed_operation


def add_parser(subparsers: SubParsers) -> None:
    build_group_parser = subparsers.add_parser(
        "build", help="build one section, game, or sibling-version family"
    )
    build_subparsers = build_group_parser.add_subparsers(
        dest="build_command", required=True
    )

    build_specs = (
        ("pokemon", "extract and enrich Pokémon and ability data", "enriched"),
        ("encounters", "extract and enrich wild encounter data", "enriched"),
        ("trainers", "extract and enrich trainer data", "enriched"),
        ("locations", "extract location data", "normalized"),
        ("moves", "extract and enrich move data", "enriched"),
        ("items", "extract and enrich item data", "enriched"),
    )
    for kind, help_text, data_label in build_specs:
        section_parser = build_subparsers.add_parser(kind, help=help_text)
        add_input_arguments(section_parser)
        section_parser.add_argument(
            "--pokedb",
            type=Path,
            help=(
                "PokéDB generation output directory "
                "(default: derived from the ROM profile)"
            ),
        )
        section_parser.add_argument(
            "--data-output",
            type=Path,
            help=f"{data_label} dataset JSON output file",
        )
        section_parser.add_argument(
            "--wiki-root",
            type=Path,
            help=(
                "game wiki root receiving public data downloads "
                "(default: site catalog entry for the matched profile)"
            ),
        )
        add_comparison_arguments(section_parser)
        add_cache_argument(section_parser)
        section_parser.set_defaults(handler=run_section_build)

    build_game_parser = build_subparsers.add_parser(
        "game", help="build every dataset and public data download for one game"
    )
    add_input_arguments(build_game_parser)
    add_comparison_arguments(build_game_parser)
    add_cache_argument(build_game_parser)
    build_game_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profile)",
    )
    build_game_parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="generated data root (default: build/data)",
    )
    build_game_parser.add_argument(
        "--wiki-root",
        type=Path,
        help="game wiki root (default: site catalog entry for the matched profile)",
    )
    build_game_parser.set_defaults(handler=run_game_build)

    family_parser = build_subparsers.add_parser(
        "family",
        help="build merged data for a sibling game-version family",
    )
    family_parser.add_argument(
        "--games",
        nargs="+",
        metavar="GAME",
        required=True,
        help="two or more game identifiers from the local game configuration",
    )
    family_parser.add_argument(
        "--versions",
        nargs="+",
        metavar="LABEL",
        help="version labels used for tagging records (default: the --games values)",
    )
    family_parser.add_argument(
        "--site-id",
        required=True,
        help="merged site identifier used for data and wiki output",
    )
    family_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    family_parser.add_argument("--profiles-dir", type=Path, default=Path("profiles"))
    family_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profiles)",
    )
    family_parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="generated data root (default: build/data)",
    )
    family_parser.add_argument(
        "--wiki-root",
        type=Path,
        help="merged game wiki root (default: resolved from --site-id)",
    )
    family_parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="ignore and replace cached clean-ROM extraction data",
    )
    add_cache_argument(family_parser)
    family_parser.set_defaults(handler=run_family_build)


def run_section_build(args: argparse.Namespace) -> None:
    result = inspect_input(args)
    with timed_operation(LOG, "Section build"):
        workflow = create_build_workflow(args, result)
        game = workflow.current.profile.id
        write_section_build(
            args.build_command,
            workflow,
            data_root=(
                args.data_output.parent.parent
                if args.data_output is not None
                else DEFAULT_DATA_ROOT / game
            ),
            wiki_root=args.wiki_root or profile_wiki_root(game),
            data_output=args.data_output,
        )


def run_game_build(args: argparse.Namespace) -> None:
    result = inspect_input(args)
    with timed_operation(LOG, "Game build"):
        workflow = create_build_workflow(args, result)
        game = workflow.current.profile.id
        write_game_build(
            workflow,
            data_root=args.data_root / game,
            wiki_root=args.wiki_root or profile_wiki_root(game),
        )


def run_family_build(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Version-family build"):
        _run_family_build(args)


def _run_family_build(args: argparse.Namespace) -> None:
    games, versions = version_family_inputs(args.games, args.versions)
    registry = LocalGameRegistry.load(args.games_config)
    game_paths = {
        version: registry.get(game_id)
        for version, game_id in zip(versions, games, strict=True)
    }
    compare_to_bases = version_family_uses_baselines(game_paths)

    current_results = {}
    for version_number, version in enumerate(versions, start=1):
        LOG.info(
            "Version-family input [%s/%s] %s: inspecting ROM",
            version_number,
            len(versions),
            version,
        )
        current_results[version] = inspect_rom(
            game_paths[version].rom(), args.profiles_dir
        )
    unmatched = [
        version for version, result in current_results.items() if result.match is None
    ]
    if unmatched:
        raise LocalConfigError(
            f"Version-family ROMs did not match game profiles: {', '.join(unmatched)}"
        )
    profiles = tuple(
        result.match.profile
        for result in current_results.values()
        if result.match is not None
    )
    pokedb = PokeDBGeneration.load(resolve_pokedb_path(args.pokedb, profiles))
    workflows = {}
    for version_number, version in enumerate(versions, start=1):
        paths = game_paths[version]
        result = current_results[version]
        if compare_to_bases:
            LOG.info(
                "Version-family baseline [%s/%s] %s: inspecting ROM",
                version_number,
                len(versions),
                version,
            )
        baseline = (
            inspect_rom(paths.rom(base=True), args.profiles_dir)
            if compare_to_bases
            else None
        )
        workflows[version] = GameBuildWorkflow(
            result,
            pokedb,
            baseline=baseline,
            baseline_cache_root=args.data_root / "baselines",
            refresh_baseline=args.refresh_baseline,
            current_cache_root=args.data_root / "cache",
            refresh_current=args.refresh_cache,
        )

    site_id = args.site_id
    write_version_family_build(
        site_id,
        workflows,
        versions,
        data_root=args.data_root / site_id,
        wiki_root=args.wiki_root or site_wiki_root(site_id),
    )


def create_build_workflow(
    args: argparse.Namespace,
    result: InspectionResult,
) -> GameBuildWorkflow:
    if result.match is None:
        raise LocalConfigError("The ROM did not match a game profile")
    pokedb = PokeDBGeneration.load(
        resolve_pokedb_path(args.pokedb, (result.match.profile,))
    )
    baseline_path = resolve_build_baseline(args)
    baseline = (
        inspect_rom(baseline_path, args.profiles_dir)
        if baseline_path is not None
        else None
    )
    data_root = getattr(args, "data_root", DEFAULT_DATA_ROOT)
    return GameBuildWorkflow(
        result,
        pokedb,
        baseline=baseline,
        baseline_cache_root=data_root / "baselines",
        refresh_baseline=args.refresh_baseline,
        current_cache_root=data_root / "cache",
        refresh_current=args.refresh_cache,
    )


def resolve_build_baseline(args: argparse.Namespace) -> Path | None:
    if args.hack_only or args.base:
        if args.base_rom is not None:
            raise LocalConfigError(
                "--base-rom cannot be combined with --hack-only or --base"
            )
        return None
    if args.base_rom is not None:
        resolved = args.base_rom.resolve()
        if not resolved.is_file():
            raise LocalConfigError(f"Base ROM image does not exist: {resolved}")
        return resolved
    if args.rom is not None:
        raise LocalConfigError(
            "Explicit ROM builds require --base-rom, or --hack-only to skip comparison"
        )
    if not args.game:
        raise LocalConfigError(
            "Comparative builds require --game or --base-rom; use --hack-only to opt out"
        )
    paths = LocalGameRegistry.load(args.games_config).get(args.game)
    if paths.base_rom is None:
        return None
    return paths.rom(base=True)
