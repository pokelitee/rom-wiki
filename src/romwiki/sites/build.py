from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
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
from romwiki.sites.catalog import SiteCatalog, SiteDefinition
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
    state_root: Path | None = None,
    runner: CommandRunner | None = None,
) -> tuple[SiteDefinition, ...]:
    selected = catalog.select(site_ids, all_published=build_all)
    ordered = tuple(
        sorted(selected, key=lambda site: (site.kind != "portal", site.order))
    )
    resolved_output = output_root.resolve()
    command_runner = runner or (
        lambda command: _run_command(command, site_url=site_url)
    )
    for site in ordered:
        _validate_generated_content(site)

    resolved_state_root = (state_root or catalog.root / ".romwiki" / "build-state")

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
            state_root=resolved_state_root,
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
                state_root=resolved_state_root,
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
                    state_root=resolved_state_root,
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
    state_root: Path,
) -> None:
    clean = True
    state = None
    state_path = state_root / f"{site.id}.json"
    output_path = site.output_path(resolved_output)
    if incremental:
        state = current_site_build_state(
            catalog, site, resolved_output, dev=dev, site_url=site_url
        )
        previous = read_site_build_state(state_path)
        reusable = can_reuse_site_output(previous, state, output_path)
        if reusable and previous is not None and (
            previous.source_files == state.source_files
        ):
            _LOG.info("MkDocs build for %s skipped; inputs are unchanged", site.id)
            return
        clean = not reusable
        _LOG.info(
            "%s build selected for %s",
            "Clean" if clean else "Incremental",
            site.id,
        )
    command = _build_command(site, resolved_output, dev=dev, clean=clean)
    _run_site_build(site, command, command_runner)
    if incremental and state is not None:
        excluded = (
            frozenset(candidate.slug for candidate in catalog.sites if candidate.slug)
            if site.output_path(resolved_output) == resolved_output
            else frozenset()
        )
        completed_state = replace(
            state,
            output_files=artifact_files(output_path, excluded_top_level=excluded),
        )
        if not completed_state.output_files:
            raise SiteError(f"MkDocs build produced no files for {site.id}: {output_path}")
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
