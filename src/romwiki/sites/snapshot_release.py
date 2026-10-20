"""Publish pinned archives to the repository's `snapshots` release."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from romwiki.util.errors import SiteError

RELEASE_TAG = "snapshots"


@dataclass(frozen=True, slots=True)
class ReleaseArchive:
    """One kind of archive in the release and the manifest that pins it."""

    prefix: str
    suffix: str
    pinned_manifest: str


FRONTEND_SNAPSHOT = ReleaseArchive(
    prefix="frontend-",
    suffix=".tar.gz",
    pinned_manifest="sites/frontend-snapshot/manifest.json",
)
POKEDB_PACKS = ReleaseArchive(
    prefix="pokedb-",
    suffix=".tar",
    pinned_manifest="sites/generator-runtime/manifest.json",
)


def publish_snapshot(
    archive: Path, kind: ReleaseArchive = FRONTEND_SNAPSHOT
) -> list[str]:
    """Upload `archive` and delete every other archive of its kind except the
    one `main` still pins, which its CI and deploys need until the new pin
    merges.

    Returns the names of the deleted archives.
    """
    keep = {archive.name, _main_archive(kind)}
    if archive.name not in _release_archives(kind):
        _gh("release", "upload", RELEASE_TAG, str(archive))
    stale = sorted(_release_archives(kind) - keep)
    for name in stale:
        _gh("release", "delete-asset", RELEASE_TAG, name, "--yes")
    return stale


def _main_archive(kind: ReleaseArchive) -> str:
    try:
        manifest = json.loads(
            _gh(
                "api",
                "-H",
                "Accept: application/vnd.github.raw",
                f"repos/{{owner}}/{{repo}}/contents/{kind.pinned_manifest}?ref=main",
            )
        )
    except SiteError as error:
        # The first archive of a new kind has no pin on `main` yet.
        if "HTTP 404" in str(error):
            return ""
        raise
    return str(manifest["archive"])


def _release_archives(kind: ReleaseArchive) -> set[str]:
    names = _gh(
        "release", "view", RELEASE_TAG, "--json", "assets", "--jq", ".assets[].name"
    )
    return {
        name
        for name in names.split()
        if name.startswith(kind.prefix) and name.endswith(kind.suffix)
    }


def _gh(*args: str) -> str:
    try:
        result = subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True
        )
    except FileNotFoundError as error:
        raise SiteError("Publishing a snapshot needs the GitHub CLI (gh)") from error
    except subprocess.CalledProcessError as error:
        raise SiteError(
            f"gh {' '.join(args[:3])} failed: {error.stderr.strip()}"
        ) from error
    return result.stdout
