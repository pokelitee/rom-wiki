"""What the browser generator downloads, and the PokéDB packs it includes.

PokéDB is not in the repository, so its packs live as one archive in the
`snapshots` release, pinned by checksum in `sites/generator-runtime/`. The
Pages build restores them and lays out the generator bundle beside the app.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

from romwiki.sites.snapshot_release import POKEDB_PACKS
from romwiki.sources.pokedb import pack_pokedb
from romwiki.util.errors import SiteError
from romwiki.util.json_io import write_json_atomic

GENERATOR_RUNTIME_SCHEMA_VERSION = 1
GENERATOR_BUNDLE_SCHEMA_VERSION = 1
# The repository files `romwiki.sites.web_build.build_wiki` reads: profiles, site
# descriptors, and the guides published with each site.
_RESOURCE_PATTERNS = (
    "profiles/**/*.toml",
    "sites/portal/site.toml",
    "sites/games/*/game.toml",
    "sites/games/*/wiki/*.md",
    "sites/games/*/wiki/docs/**/*.md",
    "sites/shared/partials/**/*",
)
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def create_pokedb_archive(pokedb_root: Path, destination: Path) -> Path:
    """Pack every `gen<N>` directory under `pokedb_root` into one archive and
    write its manifest next to it.
    """
    packs = {
        f"{path.name}.json.gz": pack_pokedb(path)
        for path in sorted(pokedb_root.glob("gen[0-9]*"))
        if path.is_dir()
    }
    if not packs:
        raise SiteError(f"No PokéDB generations found in {pokedb_root}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data in packs.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    payload = stream.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = (
        destination / f"{POKEDB_PACKS.prefix}{digest[:16]}{POKEDB_PACKS.suffix}"
    )
    archive_path.write_bytes(payload)
    write_json_atomic(
        destination / "manifest.json",
        {
            "schema_version": GENERATOR_RUNTIME_SCHEMA_VERSION,
            "archive": archive_path.name,
            "sha256": digest,
            "files": {
                name: hashlib.sha256(data).hexdigest() for name, data in packs.items()
            },
        },
    )
    return archive_path


def restore_pokedb_archive(directory: Path, output: Path) -> int:
    """Verify the archive pinned in `directory` and write its packs to `output`."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != GENERATOR_RUNTIME_SCHEMA_VERSION:
        raise SiteError("Unsupported generator runtime manifest")
    payload = (directory / manifest["archive"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
        raise SiteError(f"PokéDB archive checksum mismatch: {manifest['archive']}")
    expected: dict[str, str] = manifest["files"]
    packs: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r") as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name not in expected:
                raise SiteError(f"Unexpected PokéDB archive member: {member.name}")
            extracted = archive.extractfile(member)
            assert extracted is not None
            data = extracted.read()
            if hashlib.sha256(data).hexdigest() != expected[member.name]:
                raise SiteError(f"PokéDB pack checksum mismatch: {member.name}")
            packs[member.name] = data
    if packs.keys() != expected.keys():
        raise SiteError("PokéDB archive is missing packs")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in packs.items():
        (output / name).write_bytes(data)
    return len(packs)


def write_generator_bundle(
    root: Path, wheel: Path, packs: Path, output: Path
) -> dict[str, object]:
    """Lay out the browser generator's downloads under `output`.

    Writes the `romwiki` wheel, a zip of the repository resources, the
    PokéDB packs in `packs`, and `manifest.json` listing each with its
    checksum. Every file but the wheel, whose name the installer reads, is
    named by its checksum so browsers can cache it indefinitely.
    """
    if (
        output.is_dir()
        and any(output.iterdir())
        and not (output / "manifest.json").is_file()
    ):
        raise SiteError(f"Generator output is not an earlier bundle: {output}")
    wheel_data = wheel.read_bytes()
    wheel_digest = hashlib.sha256(wheel_data).hexdigest()
    wheel_path = f"wheel-{wheel_digest[:16]}/{wheel.name}"
    resources = _resource_zip(root)
    resources_digest = hashlib.sha256(resources).hexdigest()
    files = {
        wheel_path: wheel_data,
        f"resources-{resources_digest[:16]}.zip": resources,
    }
    pokedb = {}
    for pack in sorted(packs.glob("gen*.json.gz")):
        data = pack.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        name = pack.name.removesuffix(".json.gz")
        path = f"pokedb/{name}-{digest[:16]}.json.gz"
        files[path] = data
        pokedb[name.removeprefix("gen")] = {"path": path, "sha256": digest}
    if not pokedb:
        raise SiteError(f"No PokéDB packs found in {packs}")
    shutil.rmtree(output, ignore_errors=True)
    for path, data in files.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest: dict[str, object] = {
        "schema_version": GENERATOR_BUNDLE_SCHEMA_VERSION,
        "wheel": {"path": wheel_path, "sha256": wheel_digest},
        "resources": {
            "path": f"resources-{resources_digest[:16]}.zip",
            "sha256": resources_digest,
        },
        "pokedb": pokedb,
    }
    write_json_atomic(output / "manifest.json", manifest)
    return manifest


def _resource_zip(root: Path) -> bytes:
    paths = sorted(
        {
            path
            for pattern in _RESOURCE_PATTERNS
            for path in root.glob(pattern)
            if path.is_file()
        }
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), _ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return stream.getvalue()
