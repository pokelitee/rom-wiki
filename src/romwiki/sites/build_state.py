from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.util.errors import SiteError
from romwiki.util.inventory import (
    file_content_inventory,
    file_metadata_inventory,
    file_path_inventory,
)
from romwiki.util.json_io import write_json_atomic

BUILD_STATE_SCHEMA_VERSION = 2
_MKDOCS_PACKAGES = (
    "csscompressor",
    "htmlmin2",
    "jinja2",
    "jsmin",
    "markdown",
    "mkdocs",
    "mkdocs-material",
    "mkdocs-minify-plugin",
    "pymdown-extensions",
)


class _Digest(Protocol):
    def update(self, value: bytes, /) -> object: ...


@dataclass(frozen=True, slots=True)
class SiteBuildState:
    configuration_fingerprint: str
    output_root: str
    source_files: dict[str, str]
    output_files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": BUILD_STATE_SCHEMA_VERSION,
            "configuration_fingerprint": self.configuration_fingerprint,
            "output_root": self.output_root,
            "source_files": self.source_files,
            "output_files": self.output_files,
        }


def current_site_build_state(
    catalog: SiteCatalog,
    site: SiteDefinition,
    output_root: Path,
    *,
    dev: bool,
    site_url: str | None,
    generated_source_files: dict[str, str] | None = None,
    hash_contents: bool = False,
) -> SiteBuildState:
    """Describe a site's build inputs.

    Source files are identified by size and mtime unless `hash_contents` is
    set; content hashes survive checkouts and snapshot restores, which reset
    mtimes, so CI cache keys and reuse decisions stay stable across runs.
    """
    site_root = site.config_path.parent
    if generated_source_files is not None and site.game is not None:
        source_files = _fingerprinted_files(
            site_root / "wiki",
            relative_to=site_root,
            excluded_top_level=frozenset((*site.game.generated_sections, "changes")),
            hash_contents=hash_contents,
        )
        source_files.update(
            {
                f"wiki/{path}": metadata
                for path, metadata in generated_source_files.items()
            }
        )
    else:
        source_files = _fingerprinted_files(
            site_root / "wiki", relative_to=site_root, hash_contents=hash_contents
        )
    return SiteBuildState(
        configuration_fingerprint=_configuration_fingerprint(
            catalog, site, dev=dev, site_url=site_url
        ),
        output_root=str(output_root.resolve()),
        source_files=source_files,
    )


def site_build_fingerprint(state: SiteBuildState) -> str:
    value = json.dumps(
        {
            "configuration": state.configuration_fingerprint,
            "sources": state.source_files,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def read_site_build_state(path: Path) -> SiteBuildState | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None
        if value.get("schema_version") != BUILD_STATE_SCHEMA_VERSION:
            return None
        source_files = value["source_files"]
        output_files = value["output_files"]
        if not isinstance(source_files, dict) or not all(
            isinstance(key, str) and isinstance(digest, str)
            for key, digest in source_files.items()
        ):
            return None
        if not isinstance(output_files, dict) or not all(
            isinstance(path, str)
            and isinstance(value, str)
            and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            for path, value in output_files.items()
        ):
            return None
        configuration_fingerprint = value["configuration_fingerprint"]
        output_root = value["output_root"]
        if not isinstance(configuration_fingerprint, str) or not isinstance(
            output_root, str
        ):
            return None
        return SiteBuildState(
            configuration_fingerprint=configuration_fingerprint,
            output_root=output_root,
            source_files=source_files,
            output_files=output_files,
        )
    except (KeyError, json.JSONDecodeError, OSError, TypeError):
        return None


def write_site_build_state(path: Path, state: SiteBuildState) -> None:
    write_json_atomic(path, state.to_dict(), compact=True)


def can_reuse_site_output(
    previous: SiteBuildState | None,
    current: SiteBuildState,
    output_path: Path,
    *,
    excluded_top_level: frozenset[str] = frozenset(),
    output_files: dict[str, str] | None = None,
) -> bool:
    if previous is None or not previous.output_files:
        return False
    if (
        previous.configuration_fingerprint != current.configuration_fingerprint
        or previous.output_root != current.output_root
    ):
        return False
    inventory = (
        output_files
        if output_files is not None
        else file_path_inventory(output_path, excluded_top_level=excluded_top_level)
    )
    if inventory.keys() != previous.output_files.keys():
        return False
    # MkDocs dirty builds do not remove output for deleted sources. A clean build
    # is therefore required for deletions and renames; additions and edits are safe.
    return not (previous.source_files.keys() - current.source_files.keys())


def artifact_files(
    output_path: Path, *, excluded_top_level: frozenset[str] = frozenset()
) -> dict[str, str]:
    return file_path_inventory(output_path, excluded_top_level=excluded_top_level)


def combined_artifact_files(
    catalog: SiteCatalog, output_root: Path, state_root: Path
) -> set[str]:
    resolved_output = output_root.resolve()
    expected: set[str] = set()
    for site in catalog.published():
        state = read_site_build_state(state_root / f"{site.id}.json")
        if state is None or state.output_root != str(resolved_output):
            raise SiteError(f"Missing current build state for {site.id}")
        relative_output = (
            site.output_path(resolved_output).relative_to(resolved_output).as_posix()
        )
        prefix = "" if relative_output == "." else f"{relative_output}/"
        expected.update(f"{prefix}{path}" for path in state.output_files)
    return expected


def _configuration_fingerprint(
    catalog: SiteCatalog,
    site: SiteDefinition,
    *,
    dev: bool,
    site_url: str | None,
) -> str:
    root = catalog.root
    site_root = site.config_path.parent
    paths = [
        root / "sites" / "shared",
        root / "src" / "romwiki" / "sites" / "catalog.py",
        root / "src" / "romwiki" / "sites" / "dev_pages.py",
        root / "src" / "romwiki" / "sites" / "mkdocs_hooks.py",
        root / "pyproject.toml",
        root / "requirements",
    ]
    if site.kind == "portal":
        paths.extend(sorted((root / "sites" / "games").glob("*/game.toml")))
    paths.extend(path for path in site_root.iterdir() if path.is_file())
    digest = hashlib.sha256()
    _update(digest, "mode", "dev" if dev else "production")
    _update(digest, "site_url", site_url or "")
    _update(digest, "python", sys.version)
    for package, package_version in _package_versions():
        _update(digest, f"package:{package}", package_version)
    for path in sorted(set(paths)):
        if path.is_file():
            _update_file(digest, path, relative_to=root)
        elif path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                if "__pycache__" not in child.parts and child.suffix != ".pyc":
                    _update_file(digest, child, relative_to=root)
    return digest.hexdigest()


def _fingerprinted_files(
    root: Path,
    *,
    relative_to: Path,
    excluded_top_level: frozenset[str] = frozenset(),
    hash_contents: bool = False,
) -> dict[str, str]:
    prefix = root.relative_to(relative_to).as_posix()
    inventory = file_content_inventory if hash_contents else file_metadata_inventory
    return {
        f"{prefix}/{path}": value
        for path, value in inventory(
            root, excluded_top_level=excluded_top_level
        ).items()
    }


def _update_file(digest: _Digest, path: Path, *, relative_to: Path) -> None:
    _update(digest, path.relative_to(relative_to).as_posix(), path.read_bytes())


@cache
def _package_versions() -> tuple[tuple[str, str], ...]:
    values = []
    for package in _MKDOCS_PACKAGES:
        try:
            package_version = version(package)
        except PackageNotFoundError:
            package_version = "missing"
        values.append((package, package_version))
    return tuple(values)


def _update(digest: _Digest, key: str, value: str | bytes) -> None:
    digest.update(key.encode("utf-8"))
    digest.update(b"\0")
    digest.update(value.encode("utf-8") if isinstance(value, str) else value)
    digest.update(b"\0")
