from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from romwiki.util.errors import SiteError
from romwiki.util.json_io import (
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)

PUBLIC_DATA_MANIFEST_SCHEMA_VERSION = 1
PUBLIC_DATA_DIRECTORY = "data"
PUBLIC_DATA_MANIFEST = "manifest.json"
_MANIFEST_ENTRY_FIELDS = frozenset(
    {"kind", "path", "schema_version", "record_count", "sha256", "compressed_bytes"}
)


def write_public_dataset(
    wiki_root: Path,
    kind: str,
    dataset: dict[str, Any],
) -> None:
    """Publish one normalized dataset and refresh its site's download manifest.

    Comparison/diff data is not published here -- it's changelog data, not
    the dataset itself, so it doesn't belong in the data downloads.
    """
    data_root = wiki_root / PUBLIC_DATA_DIRECTORY
    relative_path = f"{kind}.json.gz"
    compressed = _gzip_json(dataset)
    write_bytes_atomic(data_root / relative_path, compressed)
    comparisons_dir = data_root / "comparisons"
    if comparisons_dir.is_dir():
        shutil.rmtree(comparisons_dir)
    _write_manifest(
        data_root,
        str(dataset["game"]),
        {relative_path: _manifest_entry(relative_path, dataset, compressed)},
    )


def prune_public_datasets(
    wiki_root: Path,
    enabled_kinds: set[str] | frozenset[str],
    game: str,
) -> None:
    """Remove exports for sections disabled by a complete game build."""
    data_root = wiki_root / PUBLIC_DATA_DIRECTORY
    if data_root.is_dir():
        for path in data_root.rglob("*.json.gz"):
            kind = path.name.removesuffix(".json.gz")
            if kind not in enabled_kinds:
                path.unlink()
    _write_manifest(data_root, game)


def _gzip_json(value: dict[str, Any]) -> bytes:
    source = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    stream = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as archive:
        archive.write(source)
    return stream.getvalue()


def _manifest_entry(
    relative_path: str, value: dict[str, Any], compressed: bytes
) -> dict[str, Any]:
    return {
        "kind": value.get("kind", value.get("dataset")),
        "path": relative_path,
        "schema_version": value.get("schema_version"),
        "record_count": value.get("record_count", len(value.get("records", []))),
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "compressed_bytes": len(compressed),
    }


def _describe_archive(data_root: Path, relative_path: str) -> dict[str, Any]:
    path = data_root / relative_path
    compressed = path.read_bytes()
    value = json.loads(gzip.decompress(compressed).decode("utf-8"))
    return _manifest_entry(relative_path, value, compressed)


def _reusable_manifest_entries(data_root: Path) -> dict[str, dict[str, Any]]:
    """Existing manifest entries for archives not rewritten since that manifest.

    Each section build rewrites one archive, so every other archive is
    normally still described by the previous manifest. An archive written
    after that manifest (an interrupted build, or a hand edit) is described
    from disk again instead of being trusted. Equal timestamps still count as
    unchanged because filesystem timestamps can be coarser than the gap
    between writing an archive and its manifest.
    """
    manifest_path = data_root / PUBLIC_DATA_MANIFEST
    try:
        manifest_mtime = manifest_path.stat().st_mtime_ns
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != PUBLIC_DATA_MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest.get("files"), list)
    ):
        return {}
    reusable: dict[str, dict[str, Any]] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or entry.keys() != _MANIFEST_ENTRY_FIELDS:
            continue
        relative_path = entry["path"]
        if not isinstance(relative_path, str):
            continue
        try:
            archive = (data_root / relative_path).stat()
        except OSError:
            continue
        if (
            archive.st_mtime_ns <= manifest_mtime
            and archive.st_size == entry["compressed_bytes"]
        ):
            reusable[relative_path] = entry
    return reusable


def _write_manifest(
    data_root: Path,
    game: str,
    written: dict[str, dict[str, Any]] | None = None,
) -> None:
    known = {**_reusable_manifest_entries(data_root), **(written or {})}
    entries = []
    for path in sorted(
        data_root.rglob("*.json.gz"), key=lambda value: value.as_posix()
    ):
        relative_path = path.relative_to(data_root).as_posix()
        entry = known.get(relative_path)
        entries.append(
            entry if entry is not None else _describe_archive(data_root, relative_path)
        )
    manifest = {
        "schema_version": PUBLIC_DATA_MANIFEST_SCHEMA_VERSION,
        "game": game,
        "files": entries,
    }
    write_json_atomic(data_root / PUBLIC_DATA_MANIFEST, manifest)
    write_text_atomic(data_root / "index.md", _download_index(manifest))


def _download_index(manifest: dict[str, Any]) -> str:
    lines = [
        "# Data downloads",
        "",
        "These deterministic gzip files contain the complete normalized datasets "
        "used to build this wiki. They include ROM-derived facts and PokéDB "
        "reference data, but never ROM or patch bytes.",
        "",
        "| Dataset | Download | Records | Schema |",
        "| ------- | -------- | ------: | -----: |",
    ]
    for entry in manifest["files"]:
        label = str(entry["kind"]).replace("_", " ").title()
        record_count = entry["record_count"]
        lines.append(
            f"| {label} | [{entry['path']}]({entry['path']}) | "
            f"{record_count if record_count is not None else '—'} | "
            f"{entry['schema_version']} |"
        )
    lines.extend(
        [
            "",
            "File sizes and SHA-256 checksums are listed in "
            "[the machine-readable manifest](manifest.json).",
            "",
        ]
    )
    return "\n".join(lines)


def validate_public_data(wiki_root: Path) -> None:
    data_root = wiki_root / PUBLIC_DATA_DIRECTORY
    manifest_path = data_root / PUBLIC_DATA_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SiteError(f"Invalid public data manifest: {manifest_path}") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != PUBLIC_DATA_MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest.get("files"), list)
    ):
        raise SiteError(f"Unsupported public data manifest: {manifest_path}")
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise SiteError(f"Invalid public data manifest entry: {manifest_path}")
        relative = PurePosixPath(entry["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffixes[-2:] != [".json", ".gz"]
        ):
            raise SiteError(f"Invalid public data path: {entry['path']}")
        path = data_root.joinpath(*relative.parts)
        try:
            content = path.read_bytes()
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                json.load(stream)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SiteError(f"Invalid public data archive: {path}") from error
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            raise SiteError(f"Public data checksum mismatch: {path}")
