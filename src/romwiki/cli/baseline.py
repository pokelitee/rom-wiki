"""`romwiki baseline`: manage clean-ROM baseline caches."""

from __future__ import annotations

import argparse
from pathlib import Path

from romwiki.cli.common import (
    DEFAULT_DATA_ROOT,
    LOG,
    SubParsers,
    resolve_pokedb_path,
)
from romwiki.pipeline.build.context import GameBuildContext
from romwiki.pipeline.build.sections import DATASET_KINDS
from romwiki.pipeline.extraction.identify import inspect_rom
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry
from romwiki.util.logging import timed_operation


def add_parser(subparsers: SubParsers) -> None:
    baseline_parser = subparsers.add_parser(
        "baseline", help="manage clean-ROM baseline caches"
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command", required=True
    )
    baseline_build_parser = baseline_subparsers.add_parser(
        "build", help="extract and cache a configured clean base ROM"
    )
    baseline_build_parser.add_argument("--game", required=True)
    baseline_build_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    baseline_build_parser.add_argument(
        "--profiles-dir", type=Path, default=Path("profiles")
    )
    baseline_build_parser.add_argument(
        "--pokedb",
        type=Path,
        help="PokéDB generation output directory (default: derived from the ROM profile)",
    )
    baseline_build_parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="generated data root (default: build/data)",
    )
    baseline_build_parser.add_argument(
        "--scope", nargs="+", choices=DATASET_KINDS, default=list(DATASET_KINDS)
    )
    baseline_build_parser.add_argument("--refresh", action="store_true")
    baseline_build_parser.set_defaults(handler=run_build)


def run_build(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Baseline build"):
        _build(args)


def _build(args: argparse.Namespace) -> None:
    paths = LocalGameRegistry.load(args.games_config).get(args.game)
    LOG.info("Baseline input for %s: inspecting ROM", args.game)
    result = inspect_rom(paths.rom(base=True), args.profiles_dir)
    if result.match is None:
        raise LocalConfigError("The configured base ROM did not match a game profile")
    pokedb = PokeDBGeneration.load(
        resolve_pokedb_path(args.pokedb, (result.match.profile,))
    )
    cache_root = args.data_root / "baselines" / result.match.profile.id
    context = GameBuildContext(
        result, pokedb, cache_root=cache_root, refresh=args.refresh
    )
    for dataset_number, kind in enumerate(args.scope, start=1):
        LOG.info(
            "Baseline dataset [%s/%s] %s: %s",
            dataset_number,
            len(args.scope),
            result.match.profile.id,
            kind,
        )
        getattr(context, kind)()
    print(
        f"Cached {len(args.scope)} baseline dataset groups for "
        f"{result.match.profile.id}: {cache_root}"
    )
