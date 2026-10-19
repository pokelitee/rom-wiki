"""Publish frontend snapshot archives to the repository's `snapshots` release."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from romwiki.util.errors import SiteError

RELEASE_TAG = "snapshots"
ARCHIVE_PREFIX = "frontend-"
ARCHIVE_SUFFIX = ".tar.gz"
PINNED_MANIFEST = "sites/frontend-snapshot/manifest.json"


def publish_snapshot(archive: Path) -> list[str]:
    """Upload `archive` and delete every other snapshot archive except the one
    `main` still pins, which its CI and deploys need until the new pin merges.

    Returns the names of the deleted archives.
    """
    keep = {archive.name, _main_archive()}
    if archive.name not in _release_archives():
        _gh("release", "upload", RELEASE_TAG, str(archive))
    stale = sorted(_release_archives() - keep)
    for name in stale:
        _gh("release", "delete-asset", RELEASE_TAG, name, "--yes")
    return stale


def _main_archive() -> str:
    manifest = json.loads(
        _gh(
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{{owner}}/{{repo}}/contents/{PINNED_MANIFEST}?ref=main",
        )
    )
    return str(manifest["archive"])


def _release_archives() -> set[str]:
    names = _gh(
        "release", "view", RELEASE_TAG, "--json", "assets", "--jq", ".assets[].name"
    )
    return {
        name
        for name in names.split()
        if name.startswith(ARCHIVE_PREFIX) and name.endswith(ARCHIVE_SUFFIX)
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
