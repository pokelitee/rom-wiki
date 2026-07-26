from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.snapshot import REQUIRED_WIKI_SECTIONS
from romwiki.util.errors import SiteError

CommandRunner = Callable[[Sequence[str]], None]


def build_sites(
    catalog: SiteCatalog,
    output_root: Path,
    *,
    site_ids: Sequence[str] = (),
    build_all: bool = False,
    runner: CommandRunner | None = None,
) -> tuple[SiteDefinition, ...]:
    if build_all and site_ids:
        raise SiteError("Specify site identifiers or --all, not both")
    if not build_all and not site_ids:
        raise SiteError("Specify at least one site identifier or --all")

    selected = (
        catalog.published()
        if build_all
        else tuple(catalog.get(site_id) for site_id in site_ids)
    )
    if len({site.id for site in selected}) != len(selected):
        raise SiteError("A site may only be selected once")

    ordered = tuple(
        sorted(selected, key=lambda site: (site.kind != "portal", site.order))
    )
    resolved_output = output_root.resolve()
    command_runner = runner or _run_command
    for site in ordered:
        _validate_generated_content(site)
        destination = site.output_path(resolved_output)
        command_runner(
            (
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--clean",
                "--config-file",
                str(site.config_path),
                "--site-dir",
                str(destination),
            )
        )
    return ordered


def _validate_generated_content(site: SiteDefinition) -> None:
    if site.kind != "game":
        return
    wiki_root = site.config_path.parent / "wiki"
    missing = [
        section
        for section in REQUIRED_WIKI_SECTIONS
        if not (wiki_root / section / "index.md").is_file()
    ]
    if missing:
        raise SiteError(
            f"Generated wiki content is missing for {site.id}: "
            f"{', '.join(missing)}. Restore or regenerate the wiki snapshot first."
        )


def _run_command(command: Sequence[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise SiteError(
            f"MkDocs build failed with exit code {error.returncode}"
        ) from error
