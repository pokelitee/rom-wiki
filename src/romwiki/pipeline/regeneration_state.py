from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any

from romwiki.pipeline.cache_fingerprint import (
    GENERATION_EXTRACTOR_MODULES,
    extraction_source_files,
    profile_fingerprint,
)
from romwiki.sites.catalog import SiteDefinition
from romwiki.sites.inventory import file_metadata_inventory
from romwiki.util.json_io import write_json_atomic

REGENERATION_STATE_SCHEMA_VERSION = 2
_FINGERPRINT_SCHEMA_VERSION = b"2"


def regeneration_fingerprint(
    root: Path,
    site: SiteDefinition,
    current: Sequence[Any],
    baselines: Sequence[Any | None],
    pokedb_root: Path,
) -> str:
    digest = hashlib.sha256()
    digest.update(_FINGERPRINT_SCHEMA_VERSION)
    values = []
    engines: set[str] = set()
    for result in (*current, *(value for value in baselines if value is not None)):
        profile = result.match.profile
        engines.add(profile.engine)
        values.append((result.image.hashes.sha256, profile_fingerprint(profile)))
    digest.update(json.dumps(values, sort_keys=True).encode())
    paths: set[Path] = {site.config_path.parent / "game.toml"}
    package_root = root / "src" / "romwiki"
    for directory in (
        package_root / "pipeline",
        package_root / "renderers",
        package_root / "schema",
    ):
        paths.update(
            path
            for path in directory.rglob("*.py")
            if path.resolve() != Path(__file__).resolve()
        )
    for engine in engines:
        for module in GENERATION_EXTRACTOR_MODULES:
            paths.update(
                package_root / relative
                for relative in extraction_source_files(
                    engine, f"romwiki.pipeline.{module}"
                )
            )
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


def generated_inventory(site: SiteDefinition) -> dict[str, str]:
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


def can_reuse_generation(path: Path, fingerprint: str, site: SiteDefinition) -> bool:
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


def write_regeneration_state(path: Path, fingerprint: str, site: SiteDefinition) -> None:
    write_json_atomic(
        path,
        {
            "schema_version": REGENERATION_STATE_SCHEMA_VERSION,
            "input_fingerprint": fingerprint,
            "files": generated_inventory(site),
        },
    )


def _file_digest(path: Path) -> bytes:
    metadata = path.stat()
    return _cached_file_digest(path, metadata.st_size, metadata.st_mtime_ns)


@cache
def _cached_file_digest(path: Path, _size: int, _mtime_ns: int) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()
