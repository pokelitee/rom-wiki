from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import suppress
from functools import cache
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from romwiki.pipeline.build.fingerprint import profile_fingerprint
from romwiki.sites.catalog import SiteCatalog, SiteDefinition
from romwiki.sites.data_exports import (
    PUBLIC_DATA_DIRECTORY,
    PUBLIC_DATA_MANIFEST,
    validate_public_comparisons,
    validate_public_data,
)
from romwiki.util.errors import SiteError
from romwiki.util.inventory import inventory_fingerprint, modified_too_recently
from romwiki.util.json_io import write_json_atomic

_LOG = logging.getLogger("romwiki")

SNAPSHOT_MANIFEST = ".romwiki-generated-wiki.json"
DIRECTORY_SNAPSHOT_SCHEMA_VERSION = 5
SNAPSHOT_RELEASE_REPOSITORY = "pokelitee/rom-wiki"
SNAPSHOT_RELEASE_TAG = "snapshots"
DEFAULT_SNAPSHOT_URL = (
    f"https://github.com/{SNAPSHOT_RELEASE_REPOSITORY}/releases/download/"
    f"{SNAPSHOT_RELEASE_TAG}/"
)
_ASSET_DIGEST_LENGTH = 16
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_DOWNLOAD_TIMEOUT_SECONDS = 60
_DOWNLOAD_CHUNK_SIZE = 1 << 20
# Modules that only archive or decide reuse of already generated data; they
# cannot change snapshot content. The CLI and the catalog are deliberately
# absent because they orchestrate generation.
_NON_GENERATION_SOURCES = {
    "pipeline/build/regeneration.py",
    "sites/snapshot.py",
    "sites/frontend.py",
    "sites/frontend_snapshot.py",
    "cli/frontend.py",
    "util/inventory.py",
}


def create_generated_wiki_snapshot(
    root: Path,
    output: Path,
    *,
    catalog: SiteCatalog | None = None,
    pokedb_root: Path | None = None,
) -> int:
    """Archive each published data site's generated public data downloads.

    Writes deterministic, ROM-free per-site archives and their manifest to the
    `output` directory. `pokedb_root` (the directory holding `gen<N>` PokéDB
    outputs) is recorded only as provenance; restores never need it.
    """
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
    reference_fingerprints: dict[Path, str | None] = {}
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
        reference_fingerprint = _site_reference_fingerprint(
            site, pokedb_root, reference_fingerprints
        )
        if reference_fingerprint is None and reusable:
            # Unchanged generated content keeps the provenance it was produced
            # with when this snapshot run has no PokéDB checkout to inspect.
            previous_reference = old.get("reference_data_fingerprint")
            if isinstance(previous_reference, str):
                reference_fingerprint = previous_reference
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
            "asset": snapshot_asset_name(site.id, archive_sha256),
            "file_count": len(files),
            "content_fingerprint": content_fingerprint,
            "metadata_fingerprint": metadata_fingerprint,
            "reference_data_fingerprint": reference_fingerprint,
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
    manifest = {
        "schema_version": DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
        "site": site_id,
        "file_count": len(files),
        "source_fingerprint": source_fingerprint,
    }
    _write_generated_archive(output, root, files, manifest)


def _write_generated_archive(
    output: Path,
    root: Path,
    files: list[Path],
    manifest: dict[str, object],
) -> None:
    """Write a deterministic tar.gz archive of `files` (paths under `root`),
    with `manifest` (JSON-encoded) as its first entry under
    `SNAPSHOT_MANIFEST`, atomically replacing `output`.

    Every entry -- including the manifest -- is written with a fixed
    mode/mtime, so the archive's bytes depend only on file content, not on
    when or on what platform it was built.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
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
                manifest_bytes = json.dumps(
                    manifest,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                manifest_info = tarfile.TarInfo(SNAPSHOT_MANIFEST)
                manifest_info.size = len(manifest_bytes)
                manifest_info.mode = 0o644
                manifest_info.mtime = 0
                archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
                for path in files:
                    relative = path.relative_to(root).as_posix()
                    data = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
        temporary_path.replace(output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


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


def snapshot_asset_name(site_id: str, archive_sha256: str) -> str:
    """Return the immutable, content-addressed release asset name of an archive."""
    return f"{site_id}-{archive_sha256[:_ASSET_DIGEST_LENGTH]}.tar.gz"


def restore_generated_wiki_snapshot(
    root: Path,
    directory: Path,
    *,
    site_ids: tuple[str, ...] = (),
    download_url: str = DEFAULT_SNAPSHOT_URL,
) -> int:
    """Restore a trusted snapshot while restricting writes to generated data.

    Site archives missing locally (or not matching the manifest) are
    downloaded from `download_url` into a checksum-keyed cache under
    `.romwiki/` and verified before extraction.
    """
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SiteError(
            f"Generated wiki snapshot directory is invalid: {directory}"
        ) from error
    if isinstance(manifest, dict) and manifest.get("schema_version") == 4:
        return restore_public_data_snapshot(
            root, directory, site_ids=site_ids, download_url=download_url
        )
    catalog = SiteCatalog.load(root)
    cache_root = catalog.root / ".romwiki" / "snapshot-cache"
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
            if entry["source_fingerprint"] != _site_source_fingerprint(catalog, site):
                raise SiteError(f"Generated wiki snapshot is stale for {site_id}")
            entry_file_count = entry["file_count"]
            if not isinstance(entry_file_count, int) or isinstance(
                entry_file_count, bool
            ):
                raise SiteError(
                    f"Generated wiki snapshot manifest entry is invalid: {site_id}"
                )
            archive_path = _verified_site_archive(
                archive_path,
                str(entry["asset"]),
                str(entry["archive_sha256"]),
                download_url=download_url,
                cache_root=cache_root,
            )
            restored = _restore_site_archive(
                catalog,
                site,
                archive_path,
                entry_file_count,
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


def _verified_site_archive(
    local_archive: Path,
    asset: str,
    archive_sha256: str,
    *,
    download_url: str,
    cache_root: Path,
) -> Path:
    """Return a local archive whose SHA-256 matches the manifest, downloading
    the release asset into the checksum-keyed cache when necessary."""
    if local_archive.is_file():
        if _file_sha256(local_archive) == archive_sha256:
            return local_archive
        _LOG.info(
            "Local snapshot archive %s does not match the manifest; using %s",
            local_archive,
            asset,
        )
    cached = cache_root / f"{archive_sha256}.tar.gz"
    if cached.is_file():
        if _file_sha256(cached) == archive_sha256:
            return cached
        cached.unlink()
    url = f"{download_url.rstrip('/')}/{quote(asset)}"
    _LOG.info("Downloading generated wiki snapshot %s", url)
    _download_verified(url, cached, archive_sha256)
    return cached


def _download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            digest = hashlib.sha256()
            try:
                with urllib.request.urlopen(
                    url, timeout=_DOWNLOAD_TIMEOUT_SECONDS
                ) as response:
                    while chunk := response.read(_DOWNLOAD_CHUNK_SIZE):
                        digest.update(chunk)
                        stream.write(chunk)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise SiteError(
                        f"Generated wiki snapshot asset is not published: {url}. "
                        "Upload it with `romwiki site publish-snapshot`."
                    ) from error
                raise SiteError(
                    f"Could not download generated wiki snapshot {url}: "
                    f"HTTP {error.code} {error.reason}"
                ) from error
            except (urllib.error.URLError, OSError) as error:
                reason = getattr(error, "reason", error)
                raise SiteError(
                    f"Could not download generated wiki snapshot {url}: {reason}"
                ) from error
        actual_sha256 = digest.hexdigest()
        if actual_sha256 != expected_sha256:
            raise SiteError(
                f"Downloaded generated wiki snapshot {url} has SHA-256 "
                f"{actual_sha256}, but the manifest expects {expected_sha256}"
            )
        temporary_path.replace(destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


GhRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def publish_generated_wiki_snapshot(
    directory: Path,
    *,
    repository: str = SNAPSHOT_RELEASE_REPOSITORY,
    runner: GhRunner | None = None,
) -> tuple[str, ...]:
    """Upload manifest-referenced archives missing from the snapshot release.

    Assets are content-addressed and never replaced, so manifests committed
    earlier remain restorable. Returns the names of newly uploaded assets.
    """
    run = runner or _run_gh
    sites = _read_snapshot_directory_manifest(directory)
    archives: dict[str, Path] = {}
    for site_id, entry in sorted(sites.items()):
        archive_path = directory / str(entry["archive"])
        if not archive_path.is_file():
            raise SiteError(
                f"Generated wiki snapshot archive is missing for {site_id}: "
                f"{archive_path}. Run `romwiki site snapshot` first."
            )
        if _file_sha256(archive_path) != entry["archive_sha256"]:
            raise SiteError(
                f"Generated wiki snapshot archive does not match the manifest: "
                f"{archive_path}. Run `romwiki site snapshot` first."
            )
        archives[str(entry["asset"])] = archive_path

    existing = _release_asset_names(run, repository)
    missing = sorted(asset for asset in archives if asset not in existing)
    if not missing:
        _LOG.info("Snapshot release already has all %s archives", len(archives))
        return ()
    with tempfile.TemporaryDirectory() as staging:
        uploads = []
        for asset in missing:
            # `gh release upload` names each asset after its file name.
            staged = Path(staging) / asset
            shutil.copyfile(archives[asset], staged)
            uploads.append(str(staged))
        _LOG.info("Uploading %s snapshot archives to %s", len(uploads), repository)
        # Without `--clobber`, gh refuses to replace an asset that appeared
        # concurrently, preserving immutability.
        _checked_gh(
            run,
            (
                "release",
                "upload",
                SNAPSHOT_RELEASE_TAG,
                *uploads,
                "--repo",
                repository,
            ),
        )
    return tuple(missing)


def _release_asset_names(run: GhRunner, repository: str) -> set[str]:
    view = (
        "release",
        "view",
        SNAPSHOT_RELEASE_TAG,
        "--repo",
        repository,
        "--json",
        "assets",
    )
    completed = run(("gh", *view))
    if completed.returncode != 0:
        if "not found" not in (completed.stderr or "").lower():
            raise SiteError(
                f"Could not read the {SNAPSHOT_RELEASE_TAG} release of "
                f"{repository}: {(completed.stderr or '').strip()}"
            )
        _LOG.info("Creating the %s release on %s", SNAPSHOT_RELEASE_TAG, repository)
        _checked_gh(
            run,
            (
                "release",
                "create",
                SNAPSHOT_RELEASE_TAG,
                "--repo",
                repository,
                "--title",
                "Generated wiki snapshots",
                "--notes",
                "Content-addressed generated wiki archives referenced by "
                "sites/generated-wiki/manifest.json. Assets are never replaced.",
                "--latest=false",
            ),
        )
        return set()
    try:
        assets = json.loads(completed.stdout)["assets"]
        return {str(asset["name"]) for asset in assets}
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise SiteError(
            f"Could not parse the {SNAPSHOT_RELEASE_TAG} release assets of {repository}"
        ) from error


def _checked_gh(run: GhRunner, arguments: Sequence[str]) -> None:
    completed = run(("gh", *arguments))
    if completed.returncode != 0:
        raise SiteError(
            f"GitHub CLI command failed: gh {' '.join(arguments[:2])}: "
            f"{(completed.stderr or '').strip()}"
        )


def _run_gh(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as error:
        raise SiteError(
            "The GitHub CLI (`gh`) is required to publish snapshots"
        ) from error


def restore_public_data_snapshot(
    root: Path,
    directory: Path,
    *,
    site_ids: tuple[str, ...] = (),
    download_url: str = DEFAULT_SNAPSHOT_URL,
) -> int:
    """Import downloads from pinned historical archives without restoring pages.

    Schema 4 identifies a historical publication by its committed checksum,
    independently of the current extraction source. Schema 5 uses the normal
    source-sensitive, data-only restoration path.
    """
    try:
        version = json.loads(
            (directory / "manifest.json").read_text(encoding="utf-8")
        ).get("schema_version")
    except (OSError, json.JSONDecodeError) as error:
        raise SiteError(f"Invalid snapshot directory: {directory}") from error
    if version == DIRECTORY_SNAPSHOT_SCHEMA_VERSION:
        return restore_generated_wiki_snapshot(
            root, directory, site_ids=site_ids, download_url=download_url
        )
    if version != 4:
        raise SiteError(f"Unsupported historical snapshot schema: {version}")
    catalog = SiteCatalog.load(root)
    entries = _read_snapshot_directory_manifest(directory, schema_version=4)
    selected = sorted(set(site_ids) if site_ids else entries)
    total = 0
    for site_id in selected:
        site = catalog.get(site_id)
        if site_id not in entries:
            raise SiteError(f"Historical snapshot has no site: {site_id}")
        entry = entries[site_id]
        archive_path = _verified_site_archive(
            directory / str(entry["archive"]),
            str(entry["asset"]),
            str(entry["archive_sha256"]),
            download_url=download_url,
            cache_root=catalog.root / ".romwiki/snapshot-cache",
        )
        prefix = _data_prefix(catalog, site)
        legacy_sections = {
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
        }
        with tarfile.open(archive_path, "r:gz") as archive:
            expected_count = entry["file_count"]
            assert isinstance(expected_count, int)
            _validate_site_archive_manifest(
                archive,
                archive_path,
                site_id,
                expected_count,
                str(entry["source_fingerprint"]),
                schema_version=4,
            )
            members = [
                member
                for member in archive.getmembers()
                if member.name != SNAPSHOT_MANIFEST
            ]
            if len(members) != expected_count:
                raise SiteError(
                    f"Historical snapshot file count mismatch: {archive_path}"
                )
            seen = set()
            downloads = []
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.name
                    or not path.is_relative_to(prefix.parent)
                ):
                    raise SiteError(
                        f"Invalid historical snapshot member: {member.name}"
                    )
                relative = path.relative_to(prefix.parent)
                if (
                    len(relative.parts) < 2
                    or relative.parts[0] not in legacy_sections
                    or member.name in seen
                ):
                    raise SiteError(
                        f"Invalid historical snapshot member: {member.name}"
                    )
                seen.add(member.name)
                if path.is_relative_to(prefix) and (
                    path.suffixes[-2:] == [".json", ".gz"]
                    or path == prefix / "manifest.json"
                ):
                    destination = catalog.root.joinpath(*path.parts)
                    if not destination.resolve().is_relative_to(catalog.root):
                        raise SiteError(
                            f"Historical snapshot output escapes repository: {path}"
                        )
                    downloads.append((member, destination))
            for member, destination in downloads:
                stream = archive.extractfile(member)
                if stream is None:
                    raise SiteError(f"Missing historical resource: {member.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(stream.read())
                total += 1
        validate_public_data(site.config_path.parent / "wiki")
    return total


def _read_snapshot_directory_manifest(
    directory: Path,
    *,
    schema_version: int = DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
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
        or manifest.get("schema_version") != schema_version
        or not isinstance(sites, dict)
        or not all(
            isinstance(site_id, str)
            and isinstance(entry, dict)
            and _valid_snapshot_directory_entry(site_id, entry)
            for site_id, entry in sites.items()
        )
    ):
        raise SiteError(
            "Generated wiki snapshot directory has an unsupported manifest: "
            f"{directory}"
        )
    return sites


def _valid_snapshot_directory_entry(site_id: str, entry: dict[str, object]) -> bool:
    archive = entry.get("archive")
    archive_sha256 = entry.get("archive_sha256")
    file_count = entry.get("file_count")
    reference_fingerprint = entry.get("reference_data_fingerprint")
    asset = entry.get("asset")
    return (
        _is_archive_file_name(archive)
        and isinstance(archive_sha256, str)
        and _SHA256_HEX.fullmatch(archive_sha256) is not None
        and _is_archive_file_name(asset)
        and asset == snapshot_asset_name(site_id, archive_sha256)
        and isinstance(file_count, int)
        and not isinstance(file_count, bool)
        and file_count >= 0
        and (reference_fingerprint is None or isinstance(reference_fingerprint, str))
        and all(
            isinstance(entry.get(key), str)
            for key in (
                "content_fingerprint",
                "metadata_fingerprint",
                "source_fingerprint",
            )
        )
    )


def _is_archive_file_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and PurePosixPath(value).name == value
        and "/" not in value
        and "\\" not in value
        and value.endswith(".tar.gz")
    )


def _restore_site_archive(
    catalog: SiteCatalog,
    site: SiteDefinition,
    archive_path: Path,
    expected_count: int,
    expected_source_fingerprint: str,
) -> int:
    data_prefix = _data_prefix(catalog, site)
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
            relative = _validate_snapshot_member_path(member, data_prefix)
            if (
                not catalog.root.joinpath(*relative.parts)
                .resolve()
                .is_relative_to(catalog.root)
            ):
                raise SiteError(f"Snapshot output escapes repository: {relative}")
            if relative in targets:
                raise SiteError(
                    f"Generated wiki snapshot contains duplicate path: {member.name}"
                )
            targets.add(relative)
        data_root = catalog.root.joinpath(*data_prefix.parts)
        if not data_root.resolve().is_relative_to(catalog.root):
            raise SiteError(f"Snapshot data directory escapes repository: {data_root}")
        if data_root.is_dir():
            for existing in data_root.rglob("*"):
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
    validate_public_comparisons(site.config_path.parent / "wiki")
    return count


def _validate_site_archive_manifest(
    archive: tarfile.TarFile,
    archive_path: Path,
    site_id: str,
    expected_count: int,
    expected_source_fingerprint: str,
    *,
    schema_version: int = DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
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
        or manifest.get("schema_version") != schema_version
        or manifest.get("site") != site_id
        or manifest.get("file_count") != expected_count
        or manifest.get("source_fingerprint") != expected_source_fingerprint
    ):
        raise SiteError(
            f"Generated wiki snapshot has an unsupported manifest: {archive_path}"
        )


def _generated_files_for_site(site: SiteDefinition) -> list[Path]:
    """Return the download manifest and every archive it lists.

    Only manifest-listed files are archived, so stray files left in the data
    directory never reach a snapshot.
    """
    assert site.game is not None
    wiki_root = site.config_path.parent / "wiki"
    archives = validate_public_data(wiki_root)
    data_root = wiki_root / PUBLIC_DATA_DIRECTORY
    exported = {path.relative_to(data_root).as_posix() for path in archives}
    missing = [
        section
        for section in site.game.generated_sections
        if f"{section}.json.gz" not in exported
    ]
    if missing:
        raise SiteError(
            f"Generated data is missing for {site.id}: {', '.join(missing)}"
        )
    comparisons = validate_public_comparisons(wiki_root)
    if site.id != site.game.base_game:
        missing_comparisons = [
            kind
            for kind in site.game.generated_sections
            if kind != "types"
            and not (data_root / "comparisons" / f"{kind}.json").is_file()
        ]
        if missing_comparisons:
            raise SiteError(
                f"Generated comparisons are missing for {site.id}: {', '.join(missing_comparisons)}"
            )
    files = [data_root / PUBLIC_DATA_MANIFEST, *archives, *comparisons]
    return sorted(files, key=lambda path: path.as_posix())


def _site_source_fingerprint(catalog: SiteCatalog, site: SiteDefinition) -> str:
    digest = hashlib.sha256()
    source_root = catalog.root / "src" / "romwiki"
    # Every generation-capable module is covered, including shared engine code
    # such as the registry that per-extractor import closures do not reach.
    paths = {
        path
        for path in source_root.rglob("*.py")
        if path.relative_to(source_root).as_posix() not in _NON_GENERATION_SOURCES
    }
    if site.game is not None and catalog.profile_repository is not None:
        profiles = {
            profile.id: profile for profile in catalog.profile_repository.profiles
        }
        for profile_id in site.game.profiles:
            fingerprint = profile_fingerprint(profiles[profile_id]).encode()
            digest.update(len(fingerprint).to_bytes(4, "big"))
            digest.update(fingerprint)
    paths.add(site.config_path.parent / "game.toml")
    for path in sorted(paths, key=lambda value: value.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(catalog.root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = _normalized_source_bytes(path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _site_reference_fingerprint(
    site: SiteDefinition,
    pokedb_root: Path | None,
    computed: dict[Path, str | None],
) -> str | None:
    """Fingerprint the PokéDB generation output a site is generated from, or
    return None when it is unavailable at snapshot time."""
    if pokedb_root is None or site.game is None:
        return None
    directory = (pokedb_root / f"gen{site.game.generation}").resolve()
    if directory not in computed:
        computed[directory] = (
            _reference_data_fingerprint(directory) if directory.is_dir() else None
        )
    return computed[directory]


def _reference_data_fingerprint(directory: Path) -> str:
    # Mirrors the PokéDB inputs `regeneration_fingerprint` treats as generation
    # inputs, but labels paths relative to the generation directory so the
    # value does not depend on where the PokéDB checkout lives.
    digest = hashlib.sha256()
    paths = sorted(
        (path for path in directory.rglob("*.json") if path.is_file()),
        key=lambda value: value.as_posix(),
    )
    for path in paths:
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _data_prefix(catalog: SiteCatalog, site: SiteDefinition) -> PurePosixPath:
    site_root = site.config_path.parent.relative_to(catalog.root)
    return PurePosixPath(site_root.as_posix()) / "wiki" / PUBLIC_DATA_DIRECTORY


def _validate_snapshot_member_path(
    member: tarfile.TarInfo, data_prefix: PurePosixPath
) -> PurePosixPath:
    """Validate a snapshot archive member is a regular file inside the site's
    generated data directory, with no path-traversal potential, returning its
    validated relative path.
    """
    if not member.isfile():
        raise SiteError(
            f"Generated wiki snapshot contains non-file entry: {member.name}"
        )
    relative = PurePosixPath(member.name)
    if (
        relative.is_absolute()
        or "\\" in member.name
        or ":" in member.name
        or ".." in relative.parts
        or not relative.is_relative_to(data_prefix)
    ):
        raise SiteError(f"Generated wiki snapshot contains invalid path: {member.name}")
    return relative


def _is_published_data_site(site: SiteDefinition) -> bool:
    return (
        site.kind == "game"
        and site.published
        and site.game is not None
        and site.game.data_driven
    )


def _normalized_source_bytes(path: Path) -> bytes:
    stat = path.stat()
    if modified_too_recently(stat.st_mtime_ns):
        return _read_normalized_source.__wrapped__(path, stat.st_size, stat.st_mtime_ns)
    return _read_normalized_source(path, stat.st_size, stat.st_mtime_ns)


@cache
def _read_normalized_source(path: Path, _size: int, _mtime_ns: int) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")
