from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.util.json_io import write_json_atomic

BUILD_STATE_SCHEMA_VERSION = 1
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
    output_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": BUILD_STATE_SCHEMA_VERSION,
            "configuration_fingerprint": self.configuration_fingerprint,
            "output_root": self.output_root,
            "source_files": self.source_files,
            "output_files": list(self.output_files),
        }


def current_site_build_state(
    catalog: SiteCatalog,
    site: SiteDefinition,
    output_root: Path,
    *,
    dev: bool,
    site_url: str | None,
) -> SiteBuildState:
    site_root = site.config_path.parent
    return SiteBuildState(
        configuration_fingerprint=_configuration_fingerprint(
            catalog, site, dev=dev, site_url=site_url
        ),
        output_root=str(output_root.resolve()),
        source_files=_fingerprinted_files(site_root / "wiki", relative_to=site_root),
    )


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
        if not isinstance(output_files, list) or not all(
            isinstance(path, str)
            and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            for path in output_files
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
            output_files=tuple(output_files),
        )
    except (KeyError, json.JSONDecodeError, OSError, TypeError):
        return None


def write_site_build_state(path: Path, state: SiteBuildState) -> None:
    write_json_atomic(path, state.to_dict())


def can_reuse_site_output(
    previous: SiteBuildState | None,
    current: SiteBuildState,
    output_path: Path,
) -> bool:
    if previous is None or not previous.output_files:
        return False
    if (
        previous.configuration_fingerprint != current.configuration_fingerprint
        or previous.output_root != current.output_root
    ):
        return False
    if any(not (output_path / relative).is_file() for relative in previous.output_files):
        return False
    # MkDocs dirty builds do not remove output for deleted sources. A clean build
    # is therefore required for deletions and renames; additions and edits are safe.
    return not (previous.source_files.keys() - current.source_files.keys())


def artifact_files(
    output_path: Path, *, excluded_top_level: frozenset[str] = frozenset()
) -> tuple[str, ...]:
    if not output_path.is_dir():
        return ()
    return tuple(
        relative
        for path in sorted(item for item in output_path.rglob("*") if item.is_file())
        if (relative := path.relative_to(output_path).as_posix()).split("/", 1)[0]
        not in excluded_top_level
    )


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
        root / "src" / "romwiki" / "sites",
        root / "pyproject.toml",
        root / "requirements.txt",
        *sorted((root / "sites" / "games").glob("*/game.toml")),
        root / "sites" / "portal" / "site.toml",
        *(path for path in site_root.iterdir() if path.name != "wiki"),
    ]
    digest = hashlib.sha256()
    _update(digest, "mode", "dev" if dev else "production")
    _update(digest, "site_url", site_url or "")
    _update(digest, "python", sys.version)
    for package in _MKDOCS_PACKAGES:
        try:
            package_version = version(package)
        except PackageNotFoundError:
            package_version = "missing"
        _update(digest, f"package:{package}", package_version)
    for path in sorted(set(paths)):
        if path.is_file():
            _update_file(digest, path, relative_to=root)
        elif path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                if "__pycache__" not in child.parts and child.suffix != ".pyc":
                    _update_file(digest, child, relative_to=root)
    return digest.hexdigest()


def _fingerprinted_files(root: Path, *, relative_to: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(relative_to).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _update_file(digest: _Digest, path: Path, *, relative_to: Path) -> None:
    _update(digest, path.relative_to(relative_to).as_posix(), path.read_bytes())


def _update(digest: _Digest, key: str, value: str | bytes) -> None:
    digest.update(key.encode("utf-8"))
    digest.update(b"\0")
    digest.update(value.encode("utf-8") if isinstance(value, str) else value)
    digest.update(b"\0")
