from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import subprocess
import sys

from romwiki.util.errors import SiteError
from romwiki.sites.catalog import SiteCatalog, SiteDefinition


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


def _run_command(command: Sequence[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise SiteError(f"MkDocs build failed with exit code {error.returncode}") from error
