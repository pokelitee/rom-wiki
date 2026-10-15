"""Checksum-pinned snapshots of the complete ROM-free frontend publication."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

from romwiki.sites.frontend import FRONTEND_SCHEMA_VERSION
from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_json_atomic

FRONTEND_SNAPSHOT_SCHEMA_VERSION = 1


def _publication_files(root: Path) -> list[Path]:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != FRONTEND_SCHEMA_VERSION:
        raise SiteError("Unsupported frontend publication schema")
    files = {manifest_path}
    included: dict[str, Path] = {}

    def include(relative: str) -> Path:
        if relative in included:
            return included[relative]
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
            raise SiteError(f"Invalid frontend resource: {relative}")
        files.add(candidate)
        included[relative] = candidate
        return candidate

    for game in manifest["games"]:
        for section in game["sections"].values():
            include(section["metadata_path"])
            index = json.loads(include(section["index"]).read_text(encoding="utf-8"))
            for row in index["records"]:
                include(row["chunk"])
        for comparison in game["comparisons"].values():
            include(comparison)
        for document in game["documents"]:
            include(document["path"])
        include(game["search_index"])
        for download in game["downloads"]:
            path = include(f"{game['id']}/downloads/{download['path']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != download["sha256"]:
                raise SiteError(f"Frontend download checksum mismatch: {path}")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def create_frontend_snapshot(source: Path, destination: Path) -> Path:
    source = source.resolve()
    files = _publication_files(source)
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / "frontend.tar.gz"
    checksums = {
        path.relative_to(source).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in files
    }
    with (
        temporary.open("wb") as stream,
        gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(source).as_posix())
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    archive_path = destination / f"frontend-{digest[:16]}.tar.gz"
    temporary.replace(archive_path)
    write_json_atomic(
        destination / "manifest.json",
        {
            "schema_version": FRONTEND_SNAPSHOT_SCHEMA_VERSION,
            "archive": archive_path.name,
            "sha256": digest,
            "files": checksums,
        },
    )
    return archive_path


def restore_frontend_snapshot(snapshot: Path, output: Path) -> int:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != FRONTEND_SNAPSHOT_SCHEMA_VERSION:
        raise SiteError("Unsupported frontend snapshot schema")
    archive_name = manifest.get("archive", "")
    if (
        not isinstance(archive_name, str)
        or "\\" in archive_name
        or ":" in archive_name
        or PurePosixPath(archive_name).name != archive_name
        or not archive_name.endswith(".tar.gz")
    ):
        raise SiteError("Invalid frontend snapshot archive name")
    archive_path = snapshot / archive_name
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != manifest.get("sha256"):
        raise SiteError("Frontend snapshot checksum mismatch")
    expected = manifest["files"]
    output = output.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or len(
            {member.name for member in members}
        ) != len(members):
            raise SiteError("Frontend snapshot file inventory mismatch")
        for member in members:
            path = PurePosixPath(member.name)
            target = (output / member.name).resolve()
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or not target.is_relative_to(output)
                or member.name not in expected
            ):
                raise SiteError(f"Invalid frontend snapshot member: {member.name}")
            stream = archive.extractfile(member)
            if (
                stream is None
                or hashlib.sha256(stream.read()).hexdigest() != expected[member.name]
            ):
                raise SiteError(f"Frontend resource checksum mismatch: {member.name}")
        for member in members:
            stream = archive.extractfile(member)
            assert stream is not None
            target = output / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(stream.read())
    _publication_files(output)
    return len(members)
