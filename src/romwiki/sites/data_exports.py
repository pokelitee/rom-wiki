from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any

from romwiki.schema.versions import COMPARISON_SCHEMA_VERSION
from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_bytes_atomic, write_json_atomic

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
        for path in comparisons_dir.glob("*.json.gz"):
            path.unlink()
        if not any(comparisons_dir.iterdir()):
            comparisons_dir.rmdir()
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


def write_public_comparison(
    wiki_root: Path, kind: str, comparison: dict[str, Any] | None
) -> None:
    """Keep comparison resources separate from normalized bulk downloads."""
    path = wiki_root / PUBLIC_DATA_DIRECTORY / "comparisons" / f"{kind}.json"
    if comparison is None:
        path.unlink(missing_ok=True)
    else:
        write_json_atomic(path, comparison)


def validate_public_comparisons(wiki_root: Path) -> tuple[Path, ...]:
    root = wiki_root / PUBLIC_DATA_DIRECTORY
    manifest = json.loads((root / PUBLIC_DATA_MANIFEST).read_text(encoding="utf-8"))
    files = tuple(sorted((root / "comparisons").glob("*.json")))
    for path in files:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SiteError(f"Invalid comparison resource: {path}") from error
        expected_kind = "wild_encounters" if path.stem == "encounters" else path.stem
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != COMPARISON_SCHEMA_VERSION
            or value.get("game") != manifest["game"]
            or value.get("kind") != expected_kind
            or not isinstance(value.get("records"), list)
        ):
            raise SiteError(f"Invalid comparison resource: {path}")
    return files


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
    """Existing manifest entries whose archives still match their checksum.

    Each section build rewrites one archive, so every other archive is
    normally still described by the previous manifest. Hashing the
    compressed bytes proves an entry still describes its archive without
    decompressing it; timestamps are deliberately not trusted because they
    can be coarser than the interval between writes.
    """
    manifest_path = data_root / PUBLIC_DATA_MANIFEST
    try:
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
            compressed = (data_root / relative_path).read_bytes()
        except OSError:
            continue
        if hashlib.sha256(compressed).hexdigest() == entry["sha256"]:
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


def validate_public_data(wiki_root: Path) -> tuple[Path, ...]:
    """Verify a site's download manifest and the archives it lists.

    Returns the manifest-listed archive paths, in manifest order.
    """
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
    archives = []
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
        archives.append(path)
    return tuple(archives)
