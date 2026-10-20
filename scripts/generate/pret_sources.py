"""Read files from the pret commits pinned in `pret_sources.toml`.

Downloads are cached under `.romwiki/pret-cache/<commit>/`, so a pinned file
is fetched once and every later run is offline and reproducible.
"""

from __future__ import annotations

import tomllib
import urllib.request
from pathlib import Path

from common import ROOT

_SOURCES = Path(__file__).with_name("pret_sources.toml")
_CACHE = ROOT / ".romwiki" / "pret-cache"


def pinned(project: str, kind: str = "source") -> tuple[str, str]:
    """`(repository, commit)` pinned for `project`'s `kind` ("source" or "symbols")."""
    entry = tomllib.loads(_SOURCES.read_text(encoding="utf-8"))[project]
    return entry["repository"], entry[kind]


def read(project: str, path: str, *, kind: str = "source") -> str:
    """Text of `path` at `project`'s pinned commit."""
    repository, commit = pinned(project, kind)
    cached = _CACHE / commit / path
    if not cached.is_file():
        url = f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"
        with urllib.request.urlopen(url) as response:
            data = response.read()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return cached.read_bytes().decode("utf-8")
