from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import re
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from romwiki.sites.catalog import (
    DEFAULT_GENERATED_SECTIONS,
    SiteCatalog,
    SiteDefinition,
)
from romwiki.sites.data_exports import validate_public_data
from romwiki.util.errors import SiteError

_LOG = logging.getLogger("romwiki")
_SNAPSHOT_PROGRESS_INTERVAL = 2_000
_RAW_HTML_MARKDOWN_LINK = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*(?:"[^"]*\.md(?:[#?][^"]*)?"|'[^']*\.md(?:[#?][^']*)?'|[^\s"'=<>`]*\.md(?:[#?][^\s"'=<>`]*)?)""",
    re.IGNORECASE,
)

GENERATED_WIKI_SECTIONS = (
    "pokemon",
    "abilities",
    "items",
    "moves",
    "encounters",
    "trainers",
    "locations",
    "types",
    "changes",
    "data",
)
REQUIRED_WIKI_SECTIONS = DEFAULT_GENERATED_SECTIONS
SNAPSHOT_MANIFEST = ".romwiki-generated-wiki.json"
SNAPSHOT_SCHEMA_VERSION = 2
_NON_GENERATION_SOURCES = {
    "sites/audit.py",
    "sites/build.py",
    "sites/mkdocs_hooks.py",
}


def create_generated_wiki_snapshot(
    root: Path,
    output: Path,
    *,
    catalog: SiteCatalog | None = None,
) -> int:
    """Create a deterministic, ROM-free archive of generated Markdown pages."""
    if catalog is None:
        catalog = SiteCatalog.load(root)
    elif root.resolve() != catalog.root:
        raise SiteError("Generated wiki snapshot catalog does not match its root")
    resolved_root = catalog.root
    files = _generated_files(catalog)
    resolved_output = output.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{resolved_output.name}.",
            suffix=".tmp",
            dir=resolved_output.parent,
            delete=False,
        ) as raw_stream:
            temporary_path = Path(raw_stream.name)
            with (
                gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_stream,
                    mtime=0,
                ) as gzip_stream,
                tarfile.open(fileobj=gzip_stream, mode="w") as archive,
            ):
                manifest = json.dumps(
                    {
                        "schema_version": SNAPSHOT_SCHEMA_VERSION,
                        "file_count": len(files),
                        "source_fingerprint": _source_fingerprint(resolved_root),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                manifest_info = tarfile.TarInfo(SNAPSHOT_MANIFEST)
                manifest_info.size = len(manifest)
                manifest_info.mode = 0o644
                manifest_info.mtime = 0
                archive.addfile(manifest_info, io.BytesIO(manifest))
                for file_number, path in enumerate(files, start=1):
                    relative = path.relative_to(resolved_root).as_posix()
                    data = path.read_bytes()
                    _validate_generated_link_context(path, data, resolved_root)
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
                    if file_number % _SNAPSHOT_PROGRESS_INTERVAL == 0:
                        _LOG.info(
                            "Snapshot archived %s/%s files",
                            f"{file_number:,}",
                            f"{len(files):,}",
                        )
        temporary_path.replace(resolved_output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return len(files)


def restore_generated_wiki_snapshot(root: Path, archive_path: Path) -> int:
    """Restore a trusted snapshot while restricting writes to generated sections."""
    catalog = SiteCatalog.load(root)
    resolved_root = catalog.root
    allowed_prefixes = _allowed_prefixes(catalog)
    resolved_archive = archive_path.resolve()
    if not resolved_archive.is_file():
        raise SiteError(f"Generated wiki snapshot does not exist: {resolved_archive}")

    count = 0
    try:
        with tarfile.open(resolved_archive, mode="r:gz") as archive:
            manifest = _read_snapshot_manifest(archive, resolved_archive)
            expected_fingerprint = _source_fingerprint(resolved_root)
            if manifest.get("source_fingerprint") != expected_fingerprint:
                raise SiteError(
                    "Generated wiki snapshot is stale for the current source "
                    "and profiles; regenerate it with `romwiki site snapshot`"
                )
            for member in archive:
                if member.name == SNAPSHOT_MANIFEST:
                    continue
                if not member.isfile():
                    raise SiteError(
                        f"Generated wiki snapshot contains non-file entry: {member.name}"
                    )
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not any(
                        relative.is_relative_to(prefix) for prefix in allowed_prefixes
                    )
                ):
                    raise SiteError(
                        f"Generated wiki snapshot contains invalid path: {member.name}"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise SiteError(
                        f"Could not read generated snapshot entry: {member.name}"
                    )
                destination = resolved_root.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read())
                count += 1
            if count != manifest.get("file_count"):
                raise SiteError(
                    "Generated wiki snapshot file count does not match its manifest"
                )
            for site in catalog.sites:
                if _is_published_data_site(site):
                    validate_public_data(site.config_path.parent / "wiki")
    except (tarfile.TarError, OSError) as error:
        raise SiteError(
            f"Could not restore generated wiki snapshot {resolved_archive}: {error}"
        ) from error
    return count


def _read_snapshot_manifest(
    archive: tarfile.TarFile, archive_path: Path
) -> dict[str, object]:
    try:
        member = archive.getmember(SNAPSHOT_MANIFEST)
        source = archive.extractfile(member)
        if source is None:
            raise KeyError(SNAPSHOT_MANIFEST)
        manifest = json.loads(source.read().decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SiteError(
            f"Generated wiki snapshot has no valid manifest: {archive_path}"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or not isinstance(manifest.get("file_count"), int)
        or not isinstance(manifest.get("source_fingerprint"), str)
    ):
        raise SiteError(
            f"Generated wiki snapshot has an unsupported manifest: {archive_path}"
        )
    return manifest


def _generated_files(catalog: SiteCatalog) -> list[Path]:
    files = []
    for site in catalog.published():
        if not _is_published_data_site(site):
            continue
        wiki_root = site.config_path.parent / "wiki"
        assert site.game is not None
        for section in site.game.generated_sections:
            index = wiki_root / section / "index.md"
            if not index.is_file():
                raise SiteError(
                    f"Generated wiki section is missing for {site.id}: {section}"
                )
        validate_public_data(wiki_root)
        for section in (*site.game.generated_sections, "changes"):
            section_root = wiki_root / section
            if section_root.is_dir():
                files.extend(
                    Path(directory) / name
                    for directory, _, names in os.walk(section_root)
                    for name in names
                )
    return sorted(files, key=lambda path: path.as_posix())


def _allowed_prefixes(catalog: SiteCatalog) -> tuple[PurePosixPath, ...]:
    prefixes = []
    for site in catalog.sites:
        if not _is_published_data_site(site):
            continue
        site_root = site.config_path.parent.relative_to(catalog.root)
        assert site.game is not None
        for section in (*site.game.generated_sections, "changes"):
            prefixes.append(PurePosixPath(site_root.as_posix()) / "wiki" / section)
    return tuple(prefixes)


def _validate_generated_link_context(path: Path, data: bytes, root: Path) -> None:
    if path.suffix.lower() != ".md":
        return
    text = data.decode("utf-8")
    match = _RAW_HTML_MARKDOWN_LINK.search(text)
    if match is not None:
        relative = path.relative_to(root)
        raise SiteError(
            "Generated raw HTML must use a published URL, not a Markdown "
            f"target in {relative}: {match.group(0)!r}"
        )


def _is_published_data_site(site: SiteDefinition) -> bool:
    return (
        site.kind == "game"
        and site.published
        and site.game is not None
        and site.game.data_driven
    )


def _source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    source_root = root / "src" / "romwiki"
    paths = [
        path
        for directory, pattern in (
            (source_root, "*.py"),
            (root / "profiles", "*.toml"),
        )
        if directory.is_dir()
        for path in directory.rglob(pattern)
        if path.is_file()
        and (
            directory != source_root
            or path.relative_to(source_root).as_posix() not in _NON_GENERATION_SOURCES
        )
    ]
    for path in sorted(paths, key=lambda value: value.as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        # Git normalizes tracked text to LF, but a Windows working tree may
        # expose the same file as CRLF. Fingerprints must describe the source
        # content rather than the checkout platform that created the snapshot.
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()
