"""Arguments and input resolution shared by several command groups."""

from __future__ import annotations

import argparse
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.profiles.models import GameProfile
from romwiki.sites import SiteAuditReport, SiteCatalog
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGamePaths, LocalGameRegistry
from romwiki.util.logging import timed_operation

LOG = logging.getLogger("romwiki")
DEFAULT_DATA_ROOT = Path("build/data")

type SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]


def add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rom",
        type=Path,
        help="explicit ROM path; overrides the selected local game path",
    )
    parser.add_argument(
        "--game",
        help="game identifier from the local game configuration",
    )
    parser.add_argument(
        "--base",
        action="store_true",
        help="use the selected game's clean base ROM instead of its patched ROM",
    )
    parser.add_argument(
        "--games-config",
        type=Path,
        default=Path(".local/games.toml"),
        help="local game-path configuration (default: .local/games.toml)",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("profiles"),
        help="directory containing game and hack profiles",
    )


def add_comparison_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-rom",
        type=Path,
        help="clean base ROM used for exact game-data comparisons",
    )
    parser.add_argument(
        "--hack-only",
        action="store_true",
        help="build without a clean-ROM baseline or change annotations",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="ignore and replace cached clean-ROM extraction data",
    )


def add_dev_argument(
    parser: argparse.ArgumentParser, *, help_text: str | None = None
) -> None:
    parser.add_argument(
        "--dev",
        action="store_true",
        help=help_text
        or (
            "only render the representative detail pages in the game's "
            "dev-pages.toml, keeping full catalog data; speeds up local "
            "iteration on renderer changes"
        ),
    )


def add_cache_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help=(
            "ignore and replace cached raw extraction data for the current "
            "ROM; normally unnecessary since the cache already invalidates "
            "itself when the ROM, resolved profile, or extraction source changes"
        ),
    )


def add_site_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing portal and games",
    )


def add_jobs_argument(
    parser: argparse.ArgumentParser,
    *,
    workers: str = "parallel MkDocs builds and audit page-parse workers",
) -> None:
    parser.add_argument(
        "--jobs",
        type=int,
        help=f"{workers} (default: one per CPU; 1 disables parallelism)",
    )


def inspect_input(args: argparse.Namespace) -> InspectionResult:
    """Inspect the ROM selected by `add_input_arguments` options."""
    input_rom = resolve_input_rom(args)
    LOG.info("ROM input: %s", input_rom)
    with timed_operation(LOG, "ROM inspection"):
        return inspect_rom(input_rom, args.profiles_dir)


def resolve_input_rom(args: argparse.Namespace) -> Path:
    if args.rom is not None:
        resolved = args.rom.resolve()
        if not resolved.is_file():
            raise LocalConfigError(f"ROM image does not exist: {resolved}")
        return resolved
    if not args.game:
        raise LocalConfigError(
            "Specify a ROM path or select a configured game with --game"
        )
    game = LocalGameRegistry.load(args.games_config).get(args.game)
    return game.rom(base=args.base)


def resolve_pokedb_path(
    configured: Path | None,
    profiles: Sequence[GameProfile],
) -> Path:
    if configured is not None:
        return configured
    generations = {get_engine(profile.engine).generation for profile in profiles}
    if None in generations:
        engines = ", ".join(sorted({profile.engine for profile in profiles}))
        raise LocalConfigError(
            f"Engine generation metadata is missing for: {engines}; specify --pokedb"
        )
    if len(generations) != 1:
        raise LocalConfigError(
            "Selected profiles use different generations; specify compatible profiles"
        )
    generation = generations.pop()
    return Path("../pokedb/.output") / f"gen{generation}"


def version_family_inputs(
    raw_games: Sequence[str], raw_versions: Sequence[str] | None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    games = tuple(raw_games)
    versions = tuple(raw_versions or games)
    if len(games) < 2:
        raise LocalConfigError("Version-family builds require at least two games")
    if len(versions) != len(games):
        raise LocalConfigError(
            "--versions must contain one label for every --games entry"
        )
    if len(set(versions)) != len(versions):
        raise LocalConfigError("Version labels must be unique")
    return games, versions


def version_family_uses_baselines(
    game_paths: Mapping[str, LocalGamePaths],
) -> bool:
    configured_baselines = {
        version: paths.base_rom is not None for version, paths in game_paths.items()
    }
    if len(set(configured_baselines.values())) != 1:
        raise LocalConfigError(
            "Version-family builds require every game to define base_rom or none"
        )
    return all(configured_baselines.values())


def profile_wiki_root(profile_id: str, *, root: Path = Path(".")) -> Path:
    resolved_root = root.resolve()
    if not (resolved_root / "sites").is_dir():
        return Path("sites/games") / profile_id / "wiki"
    catalog = SiteCatalog.load(resolved_root)
    matches = [
        site
        for site in catalog.sites
        if site.game is not None
        and site.game.data_driven
        and profile_id in site.game.profiles
    ]
    if len(matches) > 1:
        site_ids = ", ".join(site.id for site in matches)
        raise SiteError(
            f"Profile {profile_id} belongs to multiple game sites: {site_ids}"
        )
    if matches:
        return matches[0].config_path.parent / "wiki"
    return Path("sites/games") / profile_id / "wiki"


def site_wiki_root(site_id: str, *, root: Path = Path(".")) -> Path:
    resolved_root = root.resolve()
    if (resolved_root / "sites").is_dir():
        catalog = SiteCatalog.load(resolved_root)
        matches = [site for site in catalog.sites if site.id == site_id]
        if matches:
            return matches[0].config_path.parent / "wiki"
    return Path("sites/games") / site_id / "wiki"


def site_output(configured: Path | None, *, dev: bool) -> Path:
    if configured is not None:
        return configured
    return Path("build/mkdocs-dev" if dev else "dist")


def report_site_audit(report: SiteAuditReport) -> None:
    warning_counts = Counter(issue.code for issue in report.warnings)
    if LOG.isEnabledFor(logging.DEBUG):
        for issue in report.warnings:
            LOG.warning("%s", issue.format())
    elif warning_counts:
        summary = ", ".join(
            f"{code}={count:,}" for code, count in sorted(warning_counts.items())
        )
        LOG.warning(
            "Site audit found %s warning(s): %s; rerun with --verbose for details",
            f"{len(report.warnings):,}",
            summary,
        )
    displayed_errors = report.errors[:100]
    for issue in displayed_errors:
        LOG.error("%s", issue.format())
    if len(report.errors) > len(displayed_errors):
        LOG.error(
            "... %s additional error(s) omitted",
            f"{len(report.errors) - len(displayed_errors):,}",
        )
    largest = report.largest_page
    largest_text = (
        f"; largest: {largest[0]} ({largest[1] / 1024:.1f} KiB)" if largest else ""
    )
    LOG.info(
        "Audited %s pages and %s links%s",
        f"{report.page_count:,}",
        f"{report.link_count:,}",
        largest_text,
    )
    if not report.ok:
        raise SiteError(f"site audit found {len(report.errors):,} error(s)")
