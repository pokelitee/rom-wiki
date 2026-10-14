"""`romwiki generate` and `romwiki regenerate`: catalog-driven site workflows."""

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
    add_dev_argument,
    add_jobs_argument,
    add_site_root_argument,
    report_site_audit,
    site_output,
    version_family_inputs,
    version_family_uses_baselines,
)
from romwiki.pipeline.build.regeneration import (
    can_reuse_generation,
    regeneration_fingerprint,
    write_regeneration_state,
)
from romwiki.pipeline.build.rendering import (
    render_game_build,
    render_version_family_build,
)
from romwiki.pipeline.build.workflow import GameBuildWorkflow
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.profiles.loader import ProfileRepository
from romwiki.sites import (
    SiteCatalog,
    SiteDefinition,
    audit_site,
    build_sites,
    create_generated_wiki_snapshot,
)
from romwiki.sites.build_state import combined_artifact_files
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError, SiteError
from romwiki.util.local_config import LocalGameRegistry
from romwiki.util.logging import DATE_FORMAT, LOG_FORMAT, timed_operation

_GENERATION_JOBS_HELP = "parallel site generation workers"


def add_regenerate_parser(subparsers: SubParsers) -> None:
    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="regenerate selected game data, build sites, and audit the artifact",
    )
    regenerate_parser.add_argument("site_ids", nargs="*", help="game site identifiers")
    regenerate_parser.add_argument(
        "--all",
        action="store_true",
        dest="regenerate_all",
        help="regenerate every published data-driven game and build all sites",
    )
    regenerate_parser.add_argument(
        "--games-config", type=Path, default=Path(".local/games.toml")
    )
    regenerate_parser.add_argument(
        "--profiles-dir", type=Path, default=Path("profiles")
    )
    regenerate_parser.add_argument(
        "--pokedb-root",
        type=Path,
        default=Path("../pokedb/.output"),
        help="directory containing gen<N> PokéDB outputs",
    )
    regenerate_parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    regenerate_parser.add_argument(
        "--output",
        type=Path,
        help="artifact output directory (default: dist, or build/mkdocs-dev with --dev)",
    )
    regenerate_parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace current-ROM and clean-baseline extraction caches",
    )
    regenerate_parser.add_argument(
        "--incremental",
        action="store_true",
        help="reuse a compatible artifact and rebuild only changed MkDocs inputs",
    )
    regenerate_parser.add_argument(
        "--clean",
        action="store_true",
        help="ignore publication reuse state and rebuild generated content",
    )
    regenerate_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="update the generated-wiki snapshot after a successful audit",
    )
    regenerate_parser.add_argument(
        "--snapshot-output",
        type=Path,
        default=Path("sites/generated-wiki"),
    )
    regenerate_parser.add_argument("--max-page-kb", type=int, default=512)
    regenerate_parser.add_argument("--max-images", type=int, default=150)
    regenerate_parser.add_argument("--base-url")
    add_dev_argument(regenerate_parser)
    add_jobs_argument(
        regenerate_parser,
        workers=f"{_GENERATION_JOBS_HELP}, MkDocs builds, and audit page-parse workers",
    )
    add_site_root_argument(regenerate_parser)
    regenerate_parser.set_defaults(handler=run_regeneration)


def add_generate_parser(subparsers: SubParsers) -> None:
    generate_parser = subparsers.add_parser(
        "generate",
        help="generate data and Markdown for catalog game sites",
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
        default=Path("../pokedb/.output"),
        help="directory containing gen<N> PokéDB outputs",
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
        help="ignore generation reuse state and render selected content again",
    )
    add_dev_argument(generate_parser)
    add_jobs_argument(generate_parser, workers=_GENERATION_JOBS_HELP)
    add_site_root_argument(generate_parser)
    generate_parser.set_defaults(handler=run_generation)


def run_regeneration(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Complete regeneration"):
        _run_regeneration_steps(args)


def run_generation(args: argparse.Namespace) -> None:
    with timed_operation(LOG, "Catalog generation"):
        _run_regeneration_steps(args, build_artifact=False)


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
    dev: bool


def validate_regeneration_flags(args: argparse.Namespace) -> tuple[bool, bool]:
    """Check flag combinations upfront, returning `(dev, snapshot)`."""
    dev = getattr(args, "dev", False)
    snapshot = getattr(args, "snapshot", False)
    if snapshot and not args.regenerate_all:
        raise SiteError("--snapshot requires --all")
    if snapshot and getattr(args, "incremental", False):
        raise SiteError("--snapshot cannot be combined with --incremental")
    if snapshot and dev:
        raise SiteError("--snapshot cannot be combined with --dev")
    if getattr(args, "clean", False) and getattr(args, "incremental", False):
        raise SiteError("--clean cannot be combined with --incremental")
    return dev, snapshot


def _prepare_regeneration_sites(
    args: argparse.Namespace, catalog: SiteCatalog, *, build_artifact: bool
) -> list[_PreparedSite]:
    """Preflight every selected site: identify its ROMs/baselines against
    their profiles before any (expensive) extraction begins.
    """
    selected = catalog.select(
        args.site_ids,
        all_published=args.regenerate_all,
    )
    data_sites = tuple(
        site
        for site in selected
        if site.kind == "game" and site.game is not None and site.game.data_driven
    )
    if not build_artifact:
        unsupported = [site.id for site in selected if site not in data_sites]
        if unsupported and not args.regenerate_all:
            raise SiteError(
                "Generation requires data-driven game sites: " + ", ".join(unsupported)
            )
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
    *,
    dev: bool,
) -> None:
    """Extract, enrich, and render every preflighted site with changed inputs."""
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
            dev=dev,
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

    options = _GenerationOptions(args.data_root, args.refresh, dev)
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
        # Like parallel site builds, report the first failure only after every
        # worker has settled so no site is left half-written by an early exit.
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
        render_game_build(
            workflows[0],
            data_root=options.data_root / game.profiles[0],
            wiki_root=wiki_root,
            dev=options.dev,
        )
    else:
        _, versions = version_family_inputs(game.profiles, game.versions)
        render_version_family_build(
            site.id,
            dict(zip(versions, workflows, strict=True)),
            versions,
            data_root=options.data_root / site.id,
            wiki_root=wiki_root,
            dev=options.dev,
        )
    write_regeneration_state(generation.state_path, generation.fingerprint, site)
    LOG.info(
        "Generation [%s] %s completed in %.1fs",
        generation.progress,
        site.id,
        perf_counter() - site_started,
    )


def _run_regeneration_steps(
    args: argparse.Namespace, *, build_artifact: bool = True
) -> None:
    dev, snapshot = validate_regeneration_flags(args)
    catalog = SiteCatalog.load(args.root)
    prepared = _prepare_regeneration_sites(args, catalog, build_artifact=build_artifact)
    _generate_prepared_sites(args, prepared, dev=dev)
    # Release extraction graphs before spawning the memory-heavy MkDocs workers.
    prepared.clear()

    if not build_artifact:
        return

    output = site_output(args.output, dev=dev)

    with timed_operation(LOG, "Site builds"):
        built = build_sites(
            catalog,
            output,
            site_ids=args.site_ids,
            build_all=args.regenerate_all,
            dev=dev,
            jobs=args.jobs,
            incremental=getattr(args, "incremental", False),
            reuse_unchanged=not getattr(args, "clean", False),
            reuse_generation_state=True,
            defer_output_validation=args.regenerate_all,
            site_url=os.environ.get("ROMWIKI_SITE_URL"),
        )
    for site in built:
        LOG.info("Built %s: %s", site.id, site.output_path(output.resolve()))
    expected_files = (
        combined_artifact_files(
            catalog,
            output,
            args.root / ".romwiki" / "build-state",
        )
        if args.regenerate_all
        else None
    )

    with timed_operation(LOG, "Site audit"):
        report = audit_site(
            output,
            max_html_bytes=args.max_page_kb * 1024,
            max_images_per_page=args.max_images,
            base_url=args.base_url,
            jobs=args.jobs,
            cache_path=args.root / ".romwiki" / "audit-cache.sqlite3",
            refresh_cache=getattr(args, "clean", False),
            expected_files=expected_files,
            ignore_missing_links=dev,
        )
    report_site_audit(report)

    if snapshot:
        with timed_operation(LOG, "Generated wiki snapshot"):
            count = create_generated_wiki_snapshot(
                args.root,
                args.snapshot_output,
                catalog=catalog,
                pokedb_root=args.pokedb_root,
            )
        LOG.info(
            "Archived %s generated wiki files: %s",
            f"{count:,}",
            args.snapshot_output,
        )


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
