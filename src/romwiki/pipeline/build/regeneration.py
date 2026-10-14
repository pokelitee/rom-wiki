from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any, Protocol

from romwiki.pipeline.build.fingerprint import profile_fingerprint
from romwiki.util.inventory import file_metadata_inventory
from romwiki.util.json_io import write_json_atomic


class _GameDefinition(Protocol):
    @property
    def generated_sections(self) -> tuple[str, ...]: ...


class _SiteDefinition(Protocol):
    """Structural shape `regeneration.py` needs from `sites.catalog.SiteDefinition`.

    Defined locally (rather than importing the real type) so this pipeline
    module doesn't depend upward on the `sites` package that orchestrates it.
    Declared as read-only properties (rather than plain attributes) so the
    real, frozen `SiteDefinition` dataclass -- whose fields are read-only --
    satisfies this protocol structurally.
    """

    @property
    def config_path(self) -> Path: ...

    @property
    def game(self) -> _GameDefinition | None: ...


REGENERATION_STATE_SCHEMA_VERSION = 2
_FINGERPRINT_SCHEMA_VERSION = b"3"


def regeneration_fingerprint(
    root: Path,
    site: _SiteDefinition,
    current: Sequence[Any],
    baselines: Sequence[Any | None],
    pokedb_root: Path,
    *,
    dev: bool = False,
) -> str:
    digest = hashlib.sha256()
    digest.update(_FINGERPRINT_SCHEMA_VERSION)
    digest.update(b"dev" if dev else b"production")
    values = []
    for result in (*current, *(value for value in baselines if value is not None)):
        profile = result.match.profile
        values.append((result.image.hashes.sha256, profile_fingerprint(profile)))
    digest.update(json.dumps(values, sort_keys=True).encode())
    paths: set[Path] = {site.config_path.parent / "game.toml"}
    if dev:
        paths.add(site.config_path.parent / "dev-pages.toml")
    # Every package module is hashed rather than a computed import closure:
    # registries, PokéDB loaders, shared utilities, and site orchestration all
    # shape generated pages, and a missed dependency would ship stale output.
    paths.update((root / "src" / "romwiki").rglob("*.py"))
    paths.update(pokedb_root.rglob("*.json"))
    for path in sorted(paths):
        if path.is_file():
            label = (
                path.relative_to(root).as_posix()
                if path.is_relative_to(root)
                else str(path)
            )
            digest.update(label.encode())
            digest.update(b"\0")
            digest.update(_file_digest(path))
            digest.update(b"\0")
    return digest.hexdigest()


def generated_inventory(site: _SiteDefinition) -> dict[str, str]:
    assert site.game is not None
    wiki_root = site.config_path.parent / "wiki"
    inventory: dict[str, str] = {}
    for section in (*site.game.generated_sections, "changes"):
        section_root = wiki_root / section
        inventory.update(
            {
                f"{section}/{path}": metadata
                for path, metadata in file_metadata_inventory(section_root).items()
            }
        )
    return inventory


def can_reuse_generation(path: Path, fingerprint: str, site: _SiteDefinition) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (
        value.get("schema_version") == REGENERATION_STATE_SCHEMA_VERSION
        and value.get("input_fingerprint") == fingerprint
        and value.get("files") == generated_inventory(site)
        and bool(value.get("files"))
    )


def write_regeneration_state(
    path: Path, fingerprint: str, site: _SiteDefinition
) -> None:
    write_json_atomic(
        path,
        {
            "schema_version": REGENERATION_STATE_SCHEMA_VERSION,
            "input_fingerprint": fingerprint,
            "files": generated_inventory(site),
        },
        compact=True,
    )


def _file_digest(path: Path) -> bytes:
    metadata = path.stat()
    return _cached_file_digest(path, metadata.st_size, metadata.st_mtime_ns)


@cache
def _cached_file_digest(path: Path, _size: int, _mtime_ns: int) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()
