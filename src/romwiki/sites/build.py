from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from romwiki.sites.build_state import (
    artifact_files,
    can_reuse_site_output,
    current_site_build_state,
    read_site_build_state,
    write_site_build_state,
)
from romwiki.sites.catalog import SiteCatalog, SiteDefinition, site_display_key
from romwiki.sites.inventory import file_path_inventory, read_inventory_state
from romwiki.util.errors import SiteError

CommandRunner = Callable[[Sequence[str]], None]
_LOG = logging.getLogger("romwiki")


def build_sites(
    catalog: SiteCatalog,
    output_root: Path,
    *,
    site_ids: Sequence[str] = (),
    build_all: bool = False,
    dev: bool = False,
    site_url: str | None = None,
    jobs: int | None = None,
    incremental: bool = False,
    reuse_unchanged: bool = False,
    reuse_generation_state: bool = False,
    defer_output_validation: bool = False,
    state_root: Path | None = None,
    runner: CommandRunner | None = None,
) -> tuple[SiteDefinition, ...]:
    selected = catalog.select(site_ids, all_published=build_all)
    ordered = tuple(sorted(selected, key=site_display_key))
    resolved_output = output_root.resolve()
    command_runner = runner or (
        lambda command: _run_command(command, site_url=site_url)
    )
    verify_output = runner is None
    for site in ordered:
        _validate_generated_content(site)

    output_inventories: dict[str, dict[str, str]] = {}
    if reuse_unchanged and not defer_output_validation and resolved_output.is_dir():
        combined = file_path_inventory(resolved_output)
        slugs = frozenset(
            candidate.slug for candidate in catalog.sites if candidate.slug
        )
        for site in ordered:
            relative_output = (
                site.output_path(resolved_output)
                .relative_to(resolved_output)
                .as_posix()
            )
            if relative_output == ".":
                output_inventories[site.id] = {
                    path: value
                    for path, value in combined.items()
                    if path.split("/", 1)[0] not in slugs
                }
            else:
                prefix = f"{relative_output}/"
                output_inventories[site.id] = {
                    path.removeprefix(prefix): value
                    for path, value in combined.items()
                    if path.startswith(prefix)
                }

    resolved_state_root = state_root or catalog.root / ".romwiki" / "build-state"

    # MkDocs `--clean` empties the site directory it is given, so a site that
    # renders into the artifact root (the portal) would delete the game
    # directories nested inside it. Those roots run first and alone; everything
    # else writes to a private subdirectory and can run concurrently.
    root_sites: list[SiteDefinition] = []
    nested_sites: list[SiteDefinition] = []
    for site in ordered:
        writes_to_root = site.output_path(resolved_output) == resolved_output
        (root_sites if writes_to_root else nested_sites).append(site)

    for site in root_sites:
        _build_site(
            catalog,
            site,
            resolved_output,
            command_runner,
            dev=dev,
            site_url=site_url,
            incremental=incremental,
            reuse_unchanged=reuse_unchanged,
            state_root=resolved_state_root,
            verify_output=verify_output,
            reuse_generation_state=reuse_generation_state,
            known_output_files=output_inventories.get(site.id),
            defer_output_validation=defer_output_validation,
        )

    worker_count = _worker_count(jobs, len(nested_sites))
    if worker_count <= 1:
        for site in nested_sites:
            _build_site(
                catalog,
                site,
                resolved_output,
                command_runner,
                dev=dev,
                site_url=site_url,
                incremental=incremental,
                reuse_unchanged=reuse_unchanged,
                state_root=resolved_state_root,
                verify_output=verify_output,
                reuse_generation_state=reuse_generation_state,
                known_output_files=output_inventories.get(site.id),
                defer_output_validation=defer_output_validation,
            )
    else:
        _LOG.info(
            "Building %s sites with %s parallel MkDocs jobs",
            len(nested_sites),
            worker_count,
        )
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = [
                pool.submit(
                    _build_site,
                    catalog,
                    site,
                    resolved_output,
                    command_runner,
                    dev=dev,
                    site_url=site_url,
                    incremental=incremental,
                    reuse_unchanged=reuse_unchanged,
                    state_root=resolved_state_root,
                    verify_output=verify_output,
                    reuse_generation_state=reuse_generation_state,
                    known_output_files=output_inventories.get(site.id),
                    defer_output_validation=defer_output_validation,
                )
                for site in nested_sites
            ]
            # Surface the first failure only after every build has settled, so
            # a broken site cannot leave sibling MkDocs processes orphaned.
            errors = [future.exception() for future in futures]
        for error in errors:
            if error is not None:
                raise error
    return ordered


def _worker_count(jobs: int | None, task_count: int) -> int:
    if jobs is not None and jobs < 1:
        raise SiteError(f"Parallel job count must be at least 1: {jobs}")
    if task_count <= 1:
        return 1
    if jobs is not None:
        return min(jobs, task_count)
    return min(task_count, os.cpu_count() or 1)


def _build_command(
    site: SiteDefinition, resolved_output: Path, *, dev: bool, clean: bool = True
) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "mkdocs",
        "build",
        "--clean" if clean else "--dirty",
        "--config-file",
        str(_site_config_path(site, dev=dev)),
        "--site-dir",
        str(site.output_path(resolved_output)),
    )


def _build_site(
    catalog: SiteCatalog,
    site: SiteDefinition,
    resolved_output: Path,
    command_runner: CommandRunner,
    *,
    dev: bool,
    site_url: str | None,
    incremental: bool,
    reuse_unchanged: bool,
    state_root: Path,
    verify_output: bool,
    reuse_generation_state: bool,
    known_output_files: dict[str, str] | None,
    defer_output_validation: bool,
) -> None:
    clean = True
    state = None
    state_path = state_root / f"{site.id}.json"
    output_path = site.output_path(resolved_output)
    excluded = (
        frozenset(candidate.slug for candidate in catalog.sites if candidate.slug)
        if output_path == resolved_output
        else frozenset()
    )
    generated_source_files = (
        read_inventory_state(
            catalog.root / ".romwiki" / "generation-state" / f"{site.id}.json",
            schema_version=2,
        )
        if reuse_generation_state and site.game is not None
        else None
    )
    if incremental or reuse_unchanged:
        state = current_site_build_state(
            catalog,
            site,
            resolved_output,
            dev=dev,
            site_url=site_url,
            generated_source_files=generated_source_files,
        )
        previous = read_site_build_state(state_path)
        if (
            defer_output_validation
            and previous is not None
            and output_path != resolved_output
        ):
            # Complete regeneration compares the combined path set during the
            # audit's existing artifact discovery pass. The root portal is
            # inexpensive to inventory and must be present before nested-site
            # links can be audited.
            known_output_files = previous.output_files
        reusable = can_reuse_site_output(
            previous,
            state,
            output_path,
            excluded_top_level=excluded,
            output_files=known_output_files,
        )
        if (
            reusable
            and previous is not None
            and (previous.source_files == state.source_files)
        ):
            reused_state = replace(
                state,
                output_files=(
                    known_output_files
                    if known_output_files is not None
                    else artifact_files(output_path, excluded_top_level=excluded)
                ),
            )
            if previous.output_files != reused_state.output_files:
                write_site_build_state(state_path, reused_state)
            _LOG.info("MkDocs build for %s skipped; inputs are unchanged", site.id)
            return
        clean = not reusable or not incremental
        _LOG.info(
            "%s build selected for %s",
            "Clean" if clean else "Incremental",
            site.id,
        )
    if (
        clean
        and output_path == resolved_output
        and any((output_path / slug).exists() for slug in excluded)
    ):
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            command = _build_command(site, staging, dev=dev, clean=True)
            _run_site_build(site, command, command_runner)
            for relative in file_path_inventory(
                output_path, excluded_top_level=excluded
            ):
                (output_path / relative).unlink()
            for path in sorted(
                (item for item in output_path.rglob("*") if item.is_dir()),
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                inside_nested_site = any(
                    path.is_relative_to(output_path / slug) for slug in excluded
                )
                if path != output_path and not inside_nested_site:
                    with suppress(OSError):
                        path.rmdir()
            for source in staging.iterdir():
                source.replace(output_path / source.name)
    else:
        command = _build_command(site, resolved_output, dev=dev, clean=clean)
        _run_site_build(site, command, command_runner)
    output_files = artifact_files(output_path, excluded_top_level=excluded)
    if not output_files:
        if verify_output:
            raise SiteError(
                f"MkDocs build produced no files for {site.id}: {output_path}"
            )
        return
    if state is None:
        state = current_site_build_state(
            catalog,
            site,
            resolved_output,
            dev=dev,
            site_url=site_url,
            generated_source_files=generated_source_files,
        )
    completed_state = replace(state, output_files=output_files)
    write_site_build_state(state_path, completed_state)


def _run_site_build(
    site: SiteDefinition, command: Sequence[str], command_runner: CommandRunner
) -> None:
    started = perf_counter()
    _LOG.info("MkDocs build for %s started", site.id)
    try:
        command_runner(command)
    except Exception:
        _LOG.info(
            "MkDocs build for %s failed after %.1fs", site.id, perf_counter() - started
        )
        raise
    _LOG.info(
        "MkDocs build for %s completed in %.1fs", site.id, perf_counter() - started
    )


def _site_config_path(site: SiteDefinition, *, dev: bool) -> Path:
    if not dev:
        return site.config_path
    dev_config = site.config_path.with_name("mkdocs.dev.yml")
    if dev_config.is_file():
        return dev_config
    if site.kind == "portal":
        return site.config_path
    raise SiteError(f"Development MkDocs configuration is missing for {site.id}")


def _validate_generated_content(site: SiteDefinition) -> None:
    if site.kind != "game" or (site.game is not None and not site.game.data_driven):
        return
    assert site.game is not None
    wiki_root = site.config_path.parent / "wiki"
    missing = [
        section
        for section in site.game.generated_sections
        if not (wiki_root / section / "index.md").is_file()
    ]
    if missing:
        raise SiteError(
            f"Generated wiki content is missing for {site.id}: "
            f"{', '.join(missing)}. Restore or regenerate the wiki snapshot first."
        )


def _run_command(command: Sequence[str], *, site_url: str | None = None) -> None:
    environment = None
    if site_url is not None:
        environment = os.environ.copy()
        environment["ROMWIKI_SITE_URL"] = site_url
    # Concurrent builds would interleave their MkDocs output line by line, so
    # it is captured and replayed only when a build actually fails.
    completed = subprocess.run(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        output = (completed.stdout or "").strip()
        detail = f"\n{output}" if output else ""
        raise SiteError(
            f"MkDocs build failed with exit code {completed.returncode}{detail}"
        )
