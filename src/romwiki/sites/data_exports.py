from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any

from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_json_atomic, write_text_atomic

PUBLIC_DATA_MANIFEST_SCHEMA_VERSION = 1
PUBLIC_DATA_DIRECTORY = "data"
PUBLIC_DATA_MANIFEST = "manifest.json"


def write_public_dataset(
    wiki_root: Path,
    kind: str,
    dataset: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> None:
    """Publish one normalized dataset and refresh its site's download manifest."""
    data_root = wiki_root / PUBLIC_DATA_DIRECTORY
    _write_gzip_json(data_root / f"{kind}.json.gz", dataset)
    comparison_path = data_root / "comparisons" / f"{kind}.json.gz"
    if comparison is None:
        if comparison_path.is_file():
            comparison_path.unlink()
    else:
        _write_gzip_json(comparison_path, comparison)
    _write_manifest(data_root, str(dataset["game"]))


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


def _write_gzip_json(path: Path, value: dict[str, Any]) -> None:
    source = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    stream = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as archive:
        archive.write(source)
    content = stream.getvalue()
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _write_manifest(data_root: Path, game: str) -> None:
    entries = []
    for path in sorted(
        data_root.rglob("*.json.gz"), key=lambda value: value.as_posix()
    ):
        compressed = path.read_bytes()
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
        entries.append(
            {
                "kind": value.get("kind", value.get("dataset")),
                "path": path.relative_to(data_root).as_posix(),
                "schema_version": value.get("schema_version"),
                "record_count": value.get(
                    "record_count", len(value.get("records", []))
                ),
                "sha256": hashlib.sha256(compressed).hexdigest(),
                "compressed_bytes": len(compressed),
            }
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
        if str(entry["path"]).startswith("comparisons/"):
            label += " comparison"
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
