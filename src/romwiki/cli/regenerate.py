"""`romwiki generate` (alias `regenerate`): catalog-driven site workflows."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from romwiki.cli.common import (
    DEFAULT_DATA_ROOT,
    LOG,
    SubParsers,
    add_jobs_argument,
    add_site_root_argument,
    resolve_pokedb_root,
    version_family_inputs,
    version_family_uses_baselines,
)
from romwiki.pipeline.build.outputs import (
    write_game_build,
    write_version_family_build,
)
from romwiki.pipeline.build.regeneration import (
    can_reuse_generation,
    regeneration_fingerprint,
    write_regeneration_state,
)
from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.profiles.loader import ProfileRepository
from romwiki.sites import SiteCatalog, SiteDefinition
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGameRegistry
from romwiki.util.logging import DATE_FORMAT, LOG_FORMAT, timed_operation

_GENERATION_JOBS_HELP = "parallel site generation workers"


def add_generate_parser(subparsers: SubParsers) -> None:
    generate_parser = subparsers.add_parser(
        "generate",
        aliases=["regenerate"],
        help="generate data for catalog game sites",
    )
    generate_parser.add_argument("site_ids", nargs="*", help="game site identifiers")
    generate_parser.add_argument(
        "--all",
        action="store_true",
        dest="regenerate_all",
        help="generate every published data-driven game site",
    )
    generate_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    generate_parser.add_argument("--profiles-dir", type=Path, default=Path("profiles"))
    generate_parser.add_argument(
        "--pokedb-root",
        type=Path,
        help=(
            "directory containing gen<N> PokéDB outputs (default: the local "
            "configuration's pokedb_root, else ../pokedb/.output)"
        ),
    )
    generate_parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    generate_parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace current-ROM and clean-baseline extraction caches",
    )
    generate_parser.add_argument(
        "--clean",
        action="store_true",
        help="ignore generation reuse state and generate selected content again",
    )
    add_jobs_argument(generate_parser, workers=_GENERATION_JOBS_HELP)
    add_site_root_argument(generate_parser)
    generate_parser.set_defaults(handler=run_generation)


def run_generation(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Catalog generation"):
        _run_regeneration_steps(args)


@dataclass(frozen=True, slots=True)
class _PreparedSite:
    site: SiteDefinition
    current: tuple[InspectionResult, ...]
    baselines: tuple[InspectionResult | None, ...]
    pokedb_path: Path


@dataclass(frozen=True, slots=True)
class _SiteGeneration:
    """A preflighted site whose inputs changed, ready for a generation worker."""

    prepared: _PreparedSite
    progress: str
    state_path: Path
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _GenerationOptions:
    data_root: Path
    refresh: bool


def _prepare_regeneration_sites(
    args: argparse.Namespace, catalog: SiteCatalog
) -> list[_PreparedSite]:
    """Preflight every selected site: identify its ROMs/baselines against
    their profiles before any (expensive) extraction begins.
    """
    selected = catalog.select(
        args.site_ids,
        all_published=args.regenerate_all,
    )
    data_sites = tuple(
        site for site in selected if site.kind == "game" and site.game is not None
    )
    unsupported = [site.id for site in selected if site not in data_sites]
    if unsupported and not args.regenerate_all:
        raise SiteError("Generation requires game sites: " + ", ".join(unsupported))
    registry = LocalGameRegistry.load(args.games_config) if data_sites else None
    profiles = regeneration_profiles(catalog, args.profiles_dir) if data_sites else None
    inspections: dict[Path, InspectionResult] = {}

    prepared: list[_PreparedSite] = []
    preflight_started = perf_counter()
    LOG.info("Generation preflight: %s sites", f"{len(data_sites):,}")
    for site_number, site in enumerate(data_sites, start=1):
        assert site.game is not None
        assert profiles is not None
        LOG.info(
            "Generation preflight [%s/%s]: %s",
            site_number,
            len(data_sites),
            site.id,
        )
        pokedb_path = args.pokedb_root / f"gen{site.game.generation}"
        if not pokedb_path.is_dir():
            raise LocalConfigError(
                f"PokéDB generation output does not exist for {site.id}: "
                f"{pokedb_path.resolve()}"
            )
        assert registry is not None
        paths = tuple(registry.get(profile) for profile in site.game.profiles)
        current = []
        for profile, game_paths in zip(site.game.profiles, paths, strict=True):
            current.append(
                _validate_regeneration_rom(
                    game_paths.rom(),
                    profile,
                    args.profiles_dir,
                    profiles,
                    inspections,
                )
            )
        uses_baselines = (
            paths[0].base_rom is not None
            if len(paths) == 1
            else version_family_uses_baselines(
                dict(zip(site.game.versions, paths, strict=True))
            )
        )
        baselines: list[InspectionResult | None] = [None] * len(paths)
        if uses_baselines:
            for index, game_paths in enumerate(paths):
                baseline = _inspect_regeneration_rom(
                    game_paths.rom(base=True),
                    args.profiles_dir,
                    profiles,
                    inspections,
                )
                if baseline.match is None:
                    raise LocalConfigError(
                        f"Base ROM for {game_paths.game_id} does not match a profile"
                    )
                baselines[index] = baseline
        prepared.append(
            _PreparedSite(site, tuple(current), tuple(baselines), pokedb_path.resolve())
        )

    LOG.info(
        "Generation preflight completed in %.1fs for %s sites",
        perf_counter() - preflight_started,
        f"{len(prepared):,}",
    )
    return prepared


def _generate_prepared_sites(
    args: argparse.Namespace,
    prepared: list[_PreparedSite],
) -> None:
    """Extract, enrich, and write every preflighted site with changed inputs."""
    pending = []
    for site_number, prepared_site in enumerate(prepared, start=1):
        site = prepared_site.site
        assert site.game is not None
        progress = f"{site_number}/{len(prepared)}"
        LOG.info("Generation [%s] %s: checking inputs", progress, site.id)
        state_path = args.root / ".romwiki" / "generation-state" / f"{site.id}.json"
        input_fingerprint = regeneration_fingerprint(
            args.root.resolve(),
            site,
            prepared_site.current,
            prepared_site.baselines,
            args.pokedb_root / f"gen{site.game.generation}",
            digest_cache=args.root / ".romwiki" / "file-digests.json",
        )
        if not getattr(args, "clean", False) and can_reuse_generation(
            state_path, input_fingerprint, site
        ):
            LOG.info(
                "Generation [%s] %s skipped; inputs are unchanged",
                progress,
                site.id,
            )
            continue
        pending.append(
            _SiteGeneration(prepared_site, progress, state_path, input_fingerprint)
        )

    options = _GenerationOptions(args.data_root, args.refresh)
    groups = _cache_sharing_groups(pending)
    worker_count = _generation_worker_count(getattr(args, "jobs", None), len(groups))
    if worker_count <= 1:
        pokedb_cache: dict[Path, PokeDBGeneration] = {}
        for generation in pending:
            _generate_site(generation, options, pokedb_cache)
        return

    LOG.info(
        "Generating %s sites with %s parallel workers",
        f"{len(pending):,}",
        worker_count,
    )
    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        futures = [
            pool.submit(
                _generate_site_group_in_worker,
                group,
                options,
                logging.getLogger().level,
            )
            for group in groups
        ]
        # Report the first failure only after every worker has settled so no
        # site is left half-written by an early exit.
        errors = [future.exception() for future in futures]
    for error in errors:
        if error is not None:
            raise error


def _cache_sharing_groups(
    generations: Sequence[_SiteGeneration],
) -> list[tuple[_SiteGeneration, ...]]:
    """Group sites that share an extraction cache directory.

    Sites such as a hack and its sibling hack can use the same clean-ROM
    baseline cache. Cache writes are not safe across processes, so each group
    is generated sequentially by one worker, in catalog order.
    """
    groups: list[tuple[set[tuple[str, str]], list[int]]] = []
    for index, generation in enumerate(generations):
        keys = _cache_keys(generation.prepared)
        merged_keys = set(keys)
        merged_indexes = [index]
        remaining = []
        for group_keys, indexes in groups:
            if group_keys & keys:
                merged_keys |= group_keys
                merged_indexes.extend(indexes)
            else:
                remaining.append((group_keys, indexes))
        groups = [*remaining, (merged_keys, merged_indexes)]
    return [
        tuple(generations[index] for index in sorted(indexes))
        for _, indexes in sorted(groups, key=lambda group: min(group[1]))
    ]


def _cache_keys(prepared: _PreparedSite) -> set[tuple[str, str]]:
    keys = set()
    for root, results in (
        ("cache", prepared.current),
        ("baselines", prepared.baselines),
    ):
        for result in results:
            if result is not None and result.match is not None:
                keys.add((root, result.match.profile.id))
    return keys


def _generation_worker_count(jobs: int | None, group_count: int) -> int:
    if jobs is not None and jobs < 1:
        raise SiteError(f"Parallel job count must be at least 1: {jobs}")
    if group_count <= 1:
        return 1
    return min(jobs or os.cpu_count() or 1, group_count)


_WORKER_POKEDB: dict[Path, PokeDBGeneration] = {}


def _generate_site_group_in_worker(
    group: tuple[_SiteGeneration, ...],
    options: _GenerationOptions,
    log_level: int,
) -> None:
    for generation in group:
        site_id = generation.prepared.site.id
        logging.basicConfig(
            level=log_level,
            format=LOG_FORMAT.replace("%(message)s", f"[{site_id}] %(message)s"),
            datefmt=DATE_FORMAT,
            force=True,
        )
        try:
            _generate_site(generation, options, _WORKER_POKEDB)
        except Exception as error:
            LOG.error(
                "Generation [%s] %s failed: %s", generation.progress, site_id, error
            )
            raise


def _generate_site(
    generation: _SiteGeneration,
    options: _GenerationOptions,
    pokedb_cache: dict[Path, PokeDBGeneration],
) -> None:
    prepared = generation.prepared
    site = prepared.site
    game = site.game
    assert game is not None
    site_started = perf_counter()
    if prepared.pokedb_path not in pokedb_cache:
        pokedb_cache[prepared.pokedb_path] = PokeDBGeneration.load(prepared.pokedb_path)
    pokedb = pokedb_cache[prepared.pokedb_path]
    workflows = [
        GameBuildWorkflow(
            result,
            pokedb,
            baseline=baseline,
            baseline_cache_root=options.data_root / "baselines",
            refresh_baseline=options.refresh,
            current_cache_root=options.data_root / "cache",
            refresh_current=options.refresh,
        )
        for result, baseline in zip(prepared.current, prepared.baselines, strict=True)
    ]
    wiki_root = site.config_path.parent / "wiki"
    if len(game.profiles) == 1:
        write_game_build(
            workflows[0],
            data_root=options.data_root / game.profiles[0],
            wiki_root=wiki_root,
        )
    else:
        _, versions = version_family_inputs(game.profiles, game.versions)
        write_version_family_build(
            site.id,
            dict(zip(versions, workflows, strict=True)),
            versions,
            data_root=options.data_root / site.id,
            wiki_root=wiki_root,
        )
    write_regeneration_state(generation.state_path, generation.fingerprint, site)
    LOG.info(
        "Generation [%s] %s completed in %.1fs",
        generation.progress,
        site.id,
        perf_counter() - site_started,
    )


def _run_regeneration_steps(args: argparse.Namespace) -> None:
    args.pokedb_root = resolve_pokedb_root(args.pokedb_root, args.games_config)
    catalog = SiteCatalog.load(args.root)
    prepared = _prepare_regeneration_sites(args, catalog)
    _generate_prepared_sites(args, prepared)


def _validate_regeneration_rom(
    path: Path,
    expected_profile: str,
    profiles_dir: Path,
    profiles: ProfileRepository,
    inspections: dict[Path, InspectionResult],
) -> InspectionResult:
    result = _inspect_regeneration_rom(
        path,
        profiles_dir,
        profiles,
        inspections,
    )
    actual_profile = result.match.profile.id if result.match is not None else None
    if actual_profile != expected_profile:
        actual = actual_profile or "no profile"
        raise LocalConfigError(
            f"ROM for {expected_profile} matched {actual}, not {expected_profile}"
        )
    return result


def _inspect_regeneration_rom(
    path: Path,
    profiles_dir: Path,
    profiles: ProfileRepository,
    inspections: dict[Path, InspectionResult],
) -> InspectionResult:
    resolved = path.resolve()
    if resolved not in inspections:
        inspections[resolved] = inspect_rom(
            resolved,
            profiles_dir,
            profiles=profiles,
        )
    return inspections[resolved]


def regeneration_profiles(
    catalog: SiteCatalog,
    profiles_dir: Path,
) -> ProfileRepository:
    if (
        catalog.profile_repository is not None
        and profiles_dir.resolve() == (catalog.root / "profiles").resolve()
    ):
        return catalog.profile_repository
    return ProfileRepository.load(profiles_dir)
