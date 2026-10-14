from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Protocol

from romwiki.pipeline.build.fingerprint import profile_fingerprint
from romwiki.util.inventory import file_metadata_inventory, modified_too_recently
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
FILE_DIGEST_CACHE_SCHEMA_VERSION = 1
_SHA256_HEX = re.compile("[0-9a-f]{64}")


def regeneration_fingerprint(
    root: Path,
    site: _SiteDefinition,
    current: Sequence[Any],
    baselines: Sequence[Any | None],
    pokedb_root: Path,
    *,
    dev: bool = False,
    digest_cache: Path | None = None,
) -> str:
    """Fingerprint every input that shapes a site's generated pages.

    `digest_cache` persists file digests keyed by path, size, and modification
    time, so unchanged inputs are not re-read on every run.
    """
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
    source_root = root / "src" / "romwiki"
    paths.update(source_root.rglob("*.py"))
    paths.update(pokedb_root.rglob("*.json"))
    stored = _read_file_digests(digest_cache) if digest_cache is not None else {}
    computed: dict[str, list[Any]] = {}
    for path, metadata in sorted(_file_metadata(paths).items()):
        label = (
            path.relative_to(root).as_posix()
            if path.is_relative_to(root)
            else str(path)
        )
        key = str(path.absolute())
        entry = stored.get(key)
        if modified_too_recently(metadata.st_mtime_ns):
            # Not stored either, so the next run re-reads it once its
            # timestamp can be trusted.
            file_digest = hashlib.sha256(path.read_bytes()).digest()
        else:
            if entry is not None and entry[:2] == [
                metadata.st_size,
                metadata.st_mtime_ns,
            ]:
                file_digest = bytes.fromhex(entry[2])
            else:
                file_digest = _cached_file_digest(
                    path, metadata.st_size, metadata.st_mtime_ns
                )
            computed[key] = [
                metadata.st_size,
                metadata.st_mtime_ns,
                file_digest.hex(),
            ]
        digest.update(label.encode())
        digest.update(b"\0")
        digest.update(file_digest)
        digest.update(b"\0")
    if digest_cache is not None:
        # Entries below the directories scanned here that weren't found are
        # deleted files; entries elsewhere belong to other sites' inputs.
        scanned = tuple(
            f"{directory.absolute()}{os.sep}"
            for directory in (source_root, pokedb_root, site.config_path.parent)
        )
        retained = {
            key: value for key, value in stored.items() if not key.startswith(scanned)
        }
        _write_file_digests(digest_cache, {**retained, **computed})
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


def _file_metadata(paths: Iterable[Path]) -> dict[Path, os.stat_result]:
    """Return the metadata of each path that is a regular file.

    Listing each directory once is much cheaper than a stat call per file,
    particularly on Windows, where directory entries already carry size and
    modification time.
    """
    names_by_directory: dict[Path, set[str]] = {}
    for path in paths:
        names_by_directory.setdefault(path.parent, set()).add(path.name)
    metadata: dict[Path, os.stat_result] = {}
    for directory, names in names_by_directory.items():
        unlisted = names
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.name in unlisted:
                        unlisted.discard(entry.name)
                        if entry.is_file():
                            metadata[directory / entry.name] = entry.stat()
        except FileNotFoundError:
            continue
        # On case-insensitive filesystems a path can name a file whose listed
        # spelling differs, so fall back to a direct stat as is_file() would.
        for name in unlisted:
            path = directory / name
            try:
                value = path.stat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(value.st_mode):
                metadata[path] = value
    return metadata


def _read_file_digests(path: Path) -> dict[str, list[Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != FILE_DIGEST_CACHE_SCHEMA_VERSION
        or not isinstance(files := value.get("files"), dict)
    ):
        return {}
    return {
        key: entry
        for key, entry in files.items()
        if isinstance(entry, list)
        and len(entry) == 3
        and isinstance(entry[2], str)
        and _SHA256_HEX.fullmatch(entry[2])
    }


def _write_file_digests(path: Path, files: dict[str, list[Any]]) -> None:
    write_json_atomic(
        path,
        {"schema_version": FILE_DIGEST_CACHE_SCHEMA_VERSION, "files": files},
        compact=True,
    )


@cache
def _cached_file_digest(path: Path, _size: int, _mtime_ns: int) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()
