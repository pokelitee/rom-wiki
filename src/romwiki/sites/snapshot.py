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
from contextlib import suppress
from functools import cache
from pathlib import Path, PurePosixPath

from romwiki.pipeline.build.fingerprint import (
    GENERATION_EXTRACTOR_MODULES,
    extraction_source_files,
    profile_fingerprint,
)
from romwiki.sites.catalog import (
    DEFAULT_GENERATED_SECTIONS,
    SiteCatalog,
    SiteDefinition,
)
from romwiki.sites.data_exports import validate_public_data
from romwiki.sites.inventory import inventory_fingerprint
from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_json_atomic

_LOG = logging.getLogger("romwiki")
_SNAPSHOT_PROGRESS_INTERVAL = 2_000
_RAW_HTML_MARKDOWN_LINK = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*(?:"[^"]*\.md(?:[#?][^"]*)?"|'[^']*\.md(?:[#?][^']*)?'|[^\s"'=<>`]*\.md(?:[#?][^\s"'=<>`]*)?)""",
    re.IGNORECASE,
)

REQUIRED_WIKI_SECTIONS = DEFAULT_GENERATED_SECTIONS
SNAPSHOT_MANIFEST = ".romwiki-generated-wiki.json"
SNAPSHOT_SCHEMA_VERSION = 2
DIRECTORY_SNAPSHOT_SCHEMA_VERSION = 3
_NON_GENERATION_SOURCES = {
    "cli.py",
    "pipeline/build/regeneration.py",
    "sites/audit.py",
    "sites/build.py",
    "sites/build_state.py",
    "sites/catalog.py",
    "sites/inventory.py",
    "sites/mkdocs_hooks.py",
    "sites/server.py",
    "sites/snapshot.py",
}


def create_generated_wiki_snapshot(
    root: Path,
    output: Path,
    *,
    catalog: SiteCatalog | None = None,
) -> int:
    """Create a deterministic, ROM-free archive of generated Markdown pages."""
    if output.suffix.lower() not in {".gz", ".tgz"}:
        return _create_snapshot_directory(root, output, catalog=catalog)
    if catalog is None:
        catalog = SiteCatalog.load(root)
    elif root.resolve() != catalog.root:
        raise SiteError("Generated wiki snapshot catalog does not match its root")
    resolved_root = catalog.root
    files = _generated_files(catalog)
    _LOG.info("Snapshot: discovered %s generated files", f"{len(files):,}")
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


def restore_generated_wiki_snapshot(
    root: Path, archive_path: Path, *, site_ids: tuple[str, ...] = ()
) -> int:
    """Restore a trusted snapshot while restricting writes to generated sections."""
    catalog = SiteCatalog.load(root)
    if archive_path.is_dir():
        return _restore_snapshot_directory(catalog, archive_path, site_ids=site_ids)
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
                if count % _SNAPSHOT_PROGRESS_INTERVAL == 0:
                    _LOG.info(
                        "Snapshot restore: restored %s/%s files",
                        f"{count:,}",
                        f"{int(manifest['file_count']):,}",
                    )
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


def _create_snapshot_directory(
    root: Path, output: Path, *, catalog: SiteCatalog | None
) -> int:
    catalog = catalog or SiteCatalog.load(root)
    output.mkdir(parents=True, exist_ok=True)
    previous = {}
    manifest_path = output / "manifest.json"
    with suppress(OSError, json.JSONDecodeError, AttributeError):
        previous = json.loads(manifest_path.read_text(encoding="utf-8")).get(
            "sites", {}
        )
    entries: dict[str, dict[str, object]] = {}
    total = 0
    data_sites = tuple(
        site for site in catalog.published() if _is_published_data_site(site)
    )
    for site_number, site in enumerate(data_sites, start=1):
        progress = f"{site_number}/{len(data_sites)}"
        _LOG.info("Snapshot [%s] %s: scanning generated files", progress, site.id)
        files = _generated_files_for_site(site)
        metadata_fingerprint = _metadata_fingerprint(catalog.root, files)
        source_fingerprint = _site_source_fingerprint(catalog, site)
        archive_path = output / f"{site.id}.tar.gz"
        candidate = previous.get(site.id) if isinstance(previous, dict) else None
        old = candidate if isinstance(candidate, dict) else {}
        archive_sha256 = (
            hashlib.sha256(archive_path.read_bytes()).hexdigest()
            if archive_path.is_file()
            else ""
        )
        compatible = (
            old.get("source_fingerprint") == source_fingerprint
            and old.get("archive_sha256") == archive_sha256
        )
        content_fingerprint = old.get("content_fingerprint")
        reusable = (
            compatible
            and isinstance(content_fingerprint, str)
            and old.get("metadata_fingerprint") == metadata_fingerprint
        )
        if not reusable:
            content_fingerprint = _content_fingerprint(catalog.root, files)
            reusable = (
                compatible and old.get("content_fingerprint") == content_fingerprint
            )
        if not reusable:
            _write_site_archive(
                catalog.root,
                archive_path,
                site.id,
                files,
                source_fingerprint,
            )
            archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        outcome = "reused" if reusable else "updated"
        _LOG.info(
            "Snapshot [%s] %s: %s %s files",
            progress,
            site.id,
            outcome,
            f"{len(files):,}",
        )
        entries[site.id] = {
            "archive": archive_path.name,
            "file_count": len(files),
            "content_fingerprint": content_fingerprint,
            "metadata_fingerprint": metadata_fingerprint,
            "source_fingerprint": source_fingerprint,
            "archive_sha256": archive_sha256,
        }
        total += len(files)
    write_json_atomic(
        manifest_path,
        {
            "schema_version": DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
            "sites": entries,
        },
    )
    for path in output.glob("*.tar.gz"):
        if path.name not in {entry["archive"] for entry in entries.values()}:
            path.unlink()
    return total


def _write_site_archive(
    root: Path, output: Path, site_id: str, files: list[Path], source_fingerprint: str
) -> None:
    temporary = output.with_suffix(".tmp")
    try:
        with (
            temporary.open("wb") as raw,
            gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                mtime=0,
            ) as zipped,
            tarfile.open(fileobj=zipped, mode="w") as archive,
        ):
            manifest = json.dumps(
                {
                    "schema_version": DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
                    "site": site_id,
                    "file_count": len(files),
                    "source_fingerprint": source_fingerprint,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            info = tarfile.TarInfo(SNAPSHOT_MANIFEST)
            info.size = len(manifest)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(manifest))
            for path in files:
                data = path.read_bytes()
                _validate_generated_link_context(path, data, root)
                info = tarfile.TarInfo(path.relative_to(root).as_posix())
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()


def _metadata_fingerprint(root: Path, files: list[Path]) -> str:
    inventory = {}
    for path in files:
        stat = path.stat()
        inventory[path.relative_to(root).as_posix()] = (
            f"{stat.st_size}:{stat.st_mtime_ns}"
        )
    return inventory_fingerprint(inventory)


def _content_fingerprint(root: Path, files: list[Path]) -> str:
    return inventory_fingerprint(
        {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in files
        }
    )


def _restore_snapshot_directory(
    catalog: SiteCatalog, directory: Path, *, site_ids: tuple[str, ...]
) -> int:
    sites = _read_snapshot_directory_manifest(directory)
    selected = sorted(set(site_ids) if site_ids else sites)
    count = 0
    for site_number, site_id in enumerate(selected, start=1):
        site = catalog.get(site_id)
        entry = sites.get(site_id)
        if entry is None:
            raise SiteError(f"Generated wiki snapshot has no site: {site_id}")
        progress = f"{site_number}/{len(selected)}"
        _LOG.info("Snapshot restore [%s] %s: validating archive", progress, site_id)
        archive_path = directory / str(entry["archive"])
        try:
            if (
                hashlib.sha256(archive_path.read_bytes()).hexdigest()
                != entry["archive_sha256"]
            ):
                raise SiteError(
                    f"Generated wiki snapshot archive is corrupt: {archive_path}"
                )
            if entry["source_fingerprint"] != _site_source_fingerprint(catalog, site):
                raise SiteError(f"Generated wiki snapshot is stale for {site_id}")
            restored = _restore_site_archive(
                catalog,
                site,
                archive_path,
                int(entry["file_count"]),
                str(entry["source_fingerprint"]),
            )
            count += restored
            _LOG.info(
                "Snapshot restore [%s] %s: restored %s files",
                progress,
                site_id,
                f"{restored:,}",
            )
        except (OSError, tarfile.TarError) as error:
            raise SiteError(
                f"Could not restore generated snapshot {archive_path}: {error}"
            ) from error
    return count


def _read_snapshot_directory_manifest(
    directory: Path,
) -> dict[str, dict[str, object]]:
    manifest_path = directory / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SiteError(
            f"Generated wiki snapshot directory is invalid: {directory}"
        ) from error
    sites = manifest.get("sites") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != DIRECTORY_SNAPSHOT_SCHEMA_VERSION
        or not isinstance(sites, dict)
        or not all(
            isinstance(site_id, str)
            and isinstance(entry, dict)
            and _valid_snapshot_directory_entry(entry)
            for site_id, entry in sites.items()
        )
    ):
        raise SiteError(
            "Generated wiki snapshot directory has an unsupported manifest: "
            f"{directory}"
        )
    return sites


def _valid_snapshot_directory_entry(entry: dict[str, object]) -> bool:
    archive = entry.get("archive")
    return (
        isinstance(archive, str)
        and PurePosixPath(archive).name == archive
        and "/" not in archive
        and "\\" not in archive
        and archive.endswith(".tar.gz")
        and type(entry.get("file_count")) is int
        and int(entry["file_count"]) >= 0
        and all(
            isinstance(entry.get(key), str)
            for key in (
                "archive_sha256",
                "content_fingerprint",
                "metadata_fingerprint",
                "source_fingerprint",
            )
        )
    )


def _restore_site_archive(
    catalog: SiteCatalog,
    site: SiteDefinition,
    archive_path: Path,
    expected_count: int,
    expected_source_fingerprint: str,
) -> int:
    allowed = _allowed_prefixes(SiteCatalog(catalog.root, (site,)))
    count = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        _validate_site_archive_manifest(
            archive,
            archive_path,
            site.id,
            expected_count,
            expected_source_fingerprint,
        )
        members = [member for member in archive if member.name != SNAPSHOT_MANIFEST]
        targets: set[PurePosixPath] = set()
        for member in members:
            relative = PurePosixPath(member.name)
            if (
                not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or not any(relative.is_relative_to(prefix) for prefix in allowed)
            ):
                raise SiteError(
                    f"Generated snapshot contains invalid path: {member.name}"
                )
            if relative in targets:
                raise SiteError(
                    f"Generated snapshot contains duplicate path: {member.name}"
                )
            targets.add(relative)
        for prefix in allowed:
            section_root = catalog.root.joinpath(*prefix.parts)
            if section_root.is_dir():
                for existing in section_root.rglob("*"):
                    if (
                        existing.is_file()
                        and PurePosixPath(existing.relative_to(catalog.root).as_posix())
                        not in targets
                    ):
                        existing.unlink()
        for member in members:
            relative = PurePosixPath(member.name)
            source = archive.extractfile(member)
            if source is None:
                raise SiteError(
                    f"Could not read generated snapshot entry: {member.name}"
                )
            destination = catalog.root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read())
            count += 1
    if count != expected_count:
        raise SiteError(f"Generated snapshot file count does not match: {archive_path}")
    validate_public_data(site.config_path.parent / "wiki")
    return count


def _validate_site_archive_manifest(
    archive: tarfile.TarFile,
    archive_path: Path,
    site_id: str,
    expected_count: int,
    expected_source_fingerprint: str,
) -> None:
    try:
        if (
            sum(member.name == SNAPSHOT_MANIFEST for member in archive.getmembers())
            != 1
        ):
            raise KeyError(SNAPSHOT_MANIFEST)
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
        or manifest.get("schema_version") != DIRECTORY_SNAPSHOT_SCHEMA_VERSION
        or manifest.get("site") != site_id
        or manifest.get("file_count") != expected_count
        or manifest.get("source_fingerprint") != expected_source_fingerprint
    ):
        raise SiteError(
            f"Generated wiki snapshot has an unsupported manifest: {archive_path}"
        )


def _generated_files_for_site(site: SiteDefinition) -> list[Path]:
    assert site.game is not None
    wiki_root = site.config_path.parent / "wiki"
    validate_public_data(wiki_root)
    files = []
    for section in (*site.game.generated_sections, "changes"):
        section_root = wiki_root / section
        if section != "changes" and not (section_root / "index.md").is_file():
            raise SiteError(
                f"Generated wiki section is missing for {site.id}: {section}"
            )
        if section_root.is_dir():
            files.extend(
                Path(directory) / name
                for directory, _, names in os.walk(section_root)
                for name in names
            )
    return sorted(files, key=lambda path: path.as_posix())


def _site_source_fingerprint(catalog: SiteCatalog, site: SiteDefinition) -> str:
    digest = hashlib.sha256()
    source_root = catalog.root / "src" / "romwiki"
    paths = {
        path
        for path in source_root.rglob("*.py")
        if "engines" not in path.relative_to(source_root).parts
        and path.relative_to(source_root).as_posix() not in _NON_GENERATION_SOURCES
    }
    if site.game is not None and catalog.profile_repository is not None:
        profiles = {
            profile.id: profile for profile in catalog.profile_repository.profiles
        }
        for profile_id in site.game.profiles:
            profile = profiles[profile_id]
            digest.update(profile_fingerprint(profile).encode())
            for module in GENERATION_EXTRACTOR_MODULES:
                paths.update(
                    source_root / value
                    for value in extraction_source_files(
                        profile.engine,
                        module,
                    )
                )
    paths.add(site.config_path.parent / "game.toml")
    for path in sorted(paths):
        if not path.is_file():
            continue
        digest.update(path.relative_to(catalog.root).as_posix().encode())
        digest.update(_normalized_source_bytes(path))
    return digest.hexdigest()


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
        data = _normalized_source_bytes(path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _normalized_source_bytes(path: Path) -> bytes:
    stat = path.stat()
    return _read_normalized_source(path, stat.st_size, stat.st_mtime_ns)


@cache
def _read_normalized_source(path: Path, _size: int, _mtime_ns: int) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")
