from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from romwiki.sites.catalog import DEFAULT_GENERATED_SECTIONS, SiteCatalog
from romwiki.sites.data_exports import (
    prune_public_datasets,
    write_public_comparison,
    write_public_dataset,
)
from romwiki.sites.snapshot import (
    DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
    SNAPSHOT_MANIFEST,
    _site_source_fingerprint,
    _validate_site_archive_manifest,
    _validate_snapshot_member_path,
    create_generated_wiki_snapshot,
    publish_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
    restore_public_data_snapshot,
    snapshot_asset_name,
)
from romwiki.util.errors import SiteError


class GeneratedWikiSnapshotTests(unittest.TestCase):
    def test_data_member_paths_reject_windows_and_posix_traversal(self) -> None:
        prefix = PurePosixPath("sites/games/test-game/wiki/data")
        for name in (
            "../outside.json",
            f"{prefix}/..\\..\\outside.json",
            f"{prefix}/C:outside.json",
            f"/{prefix}/pokemon.json.gz",
        ):
            with (
                self.subTest(path=name),
                self.assertRaisesRegex(SiteError, "invalid path"),
            ):
                _validate_snapshot_member_path(tarfile.TarInfo(name), prefix)

    def test_data_snapshot_restores_separate_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = _make_site(root, sections=("pokemon", "types"))
            wiki = archive.parent.parent
            comparison = {
                "schema_version": 1,
                "kind": "pokemon",
                "game": "test-game",
                "baseline": "base",
                "records": [],
            }
            write_public_comparison(wiki, "pokemon", comparison)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            path = wiki / "data/comparisons/pokemon.json"
            path.write_text("invalid", encoding="utf-8")
            restore_generated_wiki_snapshot(root, snapshot)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), comparison)

    def test_historical_restore_imports_downloads_without_restoring_page_bodies(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            download = _make_site(root, sections=("pokemon", "types"))
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            outer_path = snapshot / "manifest.json"
            outer = json.loads(outer_path.read_text(encoding="utf-8"))
            entry = outer["sites"]["test-game"]
            archive = snapshot / entry["archive"]
            with tarfile.open(archive, "r:gz") as stream:
                resources = {
                    member.name: stream.extractfile(member).read()
                    for member in stream.getmembers()
                }
            manifest = json.loads(resources[SNAPSHOT_MANIFEST])
            manifest["schema_version"] = 4
            manifest["file_count"] += 1
            resources[SNAPSHOT_MANIFEST] = json.dumps(manifest).encode()
            resources["sites/games/test-game/wiki/pokemon/legacy.md"] = b"# Legacy page"
            with tarfile.open(archive, "w:gz") as stream:
                for name, payload in resources.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    stream.addfile(info, io.BytesIO(payload))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            entry.update(
                archive_sha256=digest,
                asset=snapshot_asset_name("test-game", digest),
                file_count=manifest["file_count"],
            )
            outer["schema_version"] = 4
            outer_path.write_text(json.dumps(outer), encoding="utf-8")
            download.write_bytes(b"corrupt")
            self.assertGreater(restore_public_data_snapshot(root, snapshot), 0)
            self.assertFalse((download.parent.parent / "pokemon/legacy.md").exists())
            with gzip.open(download, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["game"], "test-game")

    def test_directory_restore_rejects_an_unsafe_archive_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
                        "sites": {
                            "test-game": {
                                "archive": "../unsafe.tar.gz",
                                "asset": f"test-game-{'0' * 16}.tar.gz",
                                "file_count": 1,
                                "archive_sha256": "0" * 64,
                                "content_fingerprint": "content",
                                "metadata_fingerprint": "metadata",
                                "source_fingerprint": "source",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SiteError, "unsupported manifest"):
                restore_generated_wiki_snapshot(root, snapshot)

    def test_directory_restore_rejects_paths_outside_generated_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            outer_manifest_path = snapshot / "manifest.json"
            outer_manifest = json.loads(outer_manifest_path.read_text(encoding="utf-8"))
            entry = outer_manifest["sites"]["test-game"]
            archive_path = snapshot / entry["archive"]

            with tarfile.open(archive_path, "r:gz") as archive:
                site_manifest_bytes = archive.extractfile(
                    archive.getmember(SNAPSHOT_MANIFEST)
                ).read()
                members = {
                    member.name: archive.extractfile(member).read()
                    for member in archive
                    if member.name != SNAPSHOT_MANIFEST
                }
            members["../unsafe.txt"] = b"unsafe"
            with tarfile.open(archive_path, "w:gz") as archive:
                manifest_info = tarfile.TarInfo(SNAPSHOT_MANIFEST)
                manifest_info.size = len(site_manifest_bytes)
                archive.addfile(manifest_info, io.BytesIO(site_manifest_bytes))
                for name, data in members.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

            entry["archive_sha256"] = hashlib.sha256(
                archive_path.read_bytes()
            ).hexdigest()
            entry["asset"] = snapshot_asset_name("test-game", entry["archive_sha256"])
            outer_manifest_path.write_text(json.dumps(outer_manifest), encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "invalid path"):
                restore_generated_wiki_snapshot(root, snapshot)

    def test_site_archive_manifest_must_match_the_outer_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            manifest = json.loads(
                (snapshot / "manifest.json").read_text(encoding="utf-8")
            )["sites"]["test-game"]
            archive_path = snapshot / manifest["archive"]

            with (
                tarfile.open(archive_path, "r:gz") as archive,
                self.assertRaisesRegex(SiteError, "unsupported manifest"),
            ):
                _validate_site_archive_manifest(
                    archive,
                    archive_path,
                    "another-game",
                    manifest["file_count"],
                    manifest["source_fingerprint"],
                )

    def test_directory_snapshot_reuses_unchanged_site_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            snapshot = root / "snapshot"
            first_count = create_generated_wiki_snapshot(root, snapshot)
            archive = snapshot / "test-game.tar.gz"
            original = archive.read_bytes()
            original_mtime = archive.stat().st_mtime_ns

            with self.assertLogs("romwiki", level="INFO") as snapshot_logs:
                second_count = create_generated_wiki_snapshot(root, snapshot)
            generated_file.unlink()
            stale = generated_file.parent / "stale.json.gz"
            stale.write_text("stale", encoding="utf-8")
            with self.assertLogs("romwiki", level="INFO") as restore_logs:
                restored_count = restore_generated_wiki_snapshot(
                    root, snapshot, site_ids=("test-game",)
                )
            reused = archive.read_bytes()
            reused_mtime = archive.stat().st_mtime_ns
            stale_exists = stale.exists()

        self.assertEqual(second_count, first_count)
        self.assertEqual(restored_count, first_count)
        self.assertEqual(reused, original)
        self.assertEqual(reused_mtime, original_mtime)
        self.assertFalse(stale_exists)
        self.assertIn(
            "Snapshot [1/1] test-game: scanning generated files",
            "\n".join(snapshot_logs.output),
        )
        self.assertIn(
            f"Snapshot [1/1] test-game: reused {first_count:,} files",
            "\n".join(snapshot_logs.output),
        )
        self.assertIn(
            "Snapshot restore [1/1] test-game: validating archive",
            "\n".join(restore_logs.output),
        )
        self.assertIn(
            f"Snapshot restore [1/1] test-game: restored {first_count:,} files",
            "\n".join(restore_logs.output),
        )

    def test_snapshot_is_deterministic_and_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            original = generated_file.read_bytes()
            first = root / "first"
            second = root / "second"

            first_count = create_generated_wiki_snapshot(root, first)
            second_count = create_generated_wiki_snapshot(root, second)
            generated_file.unlink()
            restored_count = restore_generated_wiki_snapshot(root, first)

            self.assertEqual(first_count, len(DEFAULT_GENERATED_SECTIONS) + 1)
            self.assertEqual(second_count, first_count)
            self.assertEqual(restored_count, first_count)
            self.assertEqual(
                (first / "test-game.tar.gz").read_bytes(),
                (second / "test-game.tar.gz").read_bytes(),
            )
            self.assertEqual(generated_file.read_bytes(), original)

    def test_snapshot_honors_declared_partial_generated_sections(self) -> None:
        sections = ("pokemon", "abilities", "moves", "items", "encounters", "types")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root, sections=sections)
            snapshot = root / "snapshot"

            count = create_generated_wiki_snapshot(root, snapshot)
            with tarfile.open(snapshot / "test-game.tar.gz", "r:gz") as archive:
                names = {member.name for member in archive}

        self.assertEqual(count, len(sections) + 1)
        self.assertFalse(any(name.endswith("/trainers.json.gz") for name in names))
        self.assertFalse(any(name.endswith("/locations.json.gz") for name in names))

    def test_snapshot_requires_every_declared_section_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root, sections=("pokemon", "types"))
            data_root = root / "sites" / "games" / "test-game" / "wiki" / "data"
            (data_root / "types.json.gz").unlink()
            prune_public_datasets(data_root.parent, {"pokemon"}, "test-game")

            with self.assertRaisesRegex(SiteError, "missing for test-game: types"):
                create_generated_wiki_snapshot(root, root / "snapshot")

    def test_snapshot_archives_only_manifest_listed_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            (generated_file.parent / "index.md").write_text("stale", encoding="utf-8")
            snapshot = root / "snapshot"

            count = create_generated_wiki_snapshot(root, snapshot)
            with tarfile.open(snapshot / "test-game.tar.gz", "r:gz") as archive:
                names = {member.name for member in archive}

        self.assertEqual(count, len(DEFAULT_GENERATED_SECTIONS) + 1)
        self.assertFalse(any(name.endswith("/index.md") for name in names))

    def test_restore_rejects_snapshot_after_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            source = root / "src" / "romwiki" / "example.py"
            source.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            source.write_text("VALUE = 2\n", encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "snapshot is stale"):
                restore_generated_wiki_snapshot(root, snapshot)

    def test_source_fingerprint_is_independent_of_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            source = root / "src" / "romwiki" / "example.py"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"VALUE = 1\nOTHER = 2\n")
            catalog = SiteCatalog.load(root)
            site = catalog.get("test-game")
            lf_fingerprint = _site_source_fingerprint(catalog, site)
            source.write_bytes(b"VALUE = 1\r\nOTHER = 2\r\n")

            self.assertEqual(_site_source_fingerprint(catalog, site), lf_fingerprint)

    def test_source_fingerprint_ignores_snapshot_only_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            module = root / "src" / "romwiki" / "sites" / "snapshot.py"
            module.parent.mkdir(parents=True)
            module.write_text("VALUE = 1\n", encoding="utf-8")
            catalog = SiteCatalog.load(root)
            site = catalog.get("test-game")
            original = _site_source_fingerprint(catalog, site)
            module.write_text("VALUE = 2\n", encoding="utf-8")

            self.assertEqual(_site_source_fingerprint(catalog, site), original)

    def test_snapshot_ignores_published_documentation_only_games(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            documentation = root / "sites" / "games" / "documentation"
            documentation.mkdir(parents=True)
            (documentation / "game.toml").write_text(
                """
[site]
id = "documentation"
name = "Documentation"
kind = "game"
slug = "documentation"
published = true
order = 2
[game]
data_driven = false
generation = 1
base_game = "documentation"
platform = "nintendo-ds"
platform_name = "Nintendo DS"
creator = "Tester"
[appearance]
theme = "platinum"
""".strip(),
                encoding="utf-8",
            )
            snapshot = root / "snapshot"

            count = create_generated_wiki_snapshot(root, snapshot)
            restored_count = restore_generated_wiki_snapshot(root, snapshot)

            self.assertEqual(count, len(DEFAULT_GENERATED_SECTIONS) + 1)
            self.assertEqual(restored_count, count)


class PublishedSnapshotTests(unittest.TestCase):
    def test_manifest_records_content_addressed_assets_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            pokedb = root / "pokedb"
            (pokedb / "gen1").mkdir(parents=True)
            (pokedb / "gen1" / "species.json").write_text("{}", encoding="utf-8")
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot, pokedb_root=pokedb)
            with_provenance = _manifest_entry(snapshot)
            create_generated_wiki_snapshot(root, snapshot)
            carried_over = _manifest_entry(snapshot)
            (pokedb / "gen1" / "species.json").write_text("[]", encoding="utf-8")
            create_generated_wiki_snapshot(root, snapshot, pokedb_root=pokedb)
            updated_provenance = _manifest_entry(snapshot)
            manifest = json.loads(
                (snapshot / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["schema_version"], DIRECTORY_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(
            with_provenance["asset"],
            f"test-game-{with_provenance['archive_sha256'][:16]}.tar.gz",
        )
        self.assertIsInstance(with_provenance["reference_data_fingerprint"], str)
        self.assertEqual(
            carried_over["reference_data_fingerprint"],
            with_provenance["reference_data_fingerprint"],
        )
        self.assertNotEqual(
            updated_provenance["reference_data_fingerprint"],
            with_provenance["reference_data_fingerprint"],
        )

    def test_restore_downloads_and_caches_a_missing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            snapshot, release = _published_snapshot(root)
            generated_file.unlink()

            restored = restore_generated_wiki_snapshot(
                root, snapshot, download_url=release.as_uri()
            )
            cached = list((root / ".romwiki" / "snapshot-cache").iterdir())
            for asset in release.iterdir():
                asset.unlink()
            restored_from_cache = restore_generated_wiki_snapshot(
                root, snapshot, download_url=release.as_uri()
            )
            generated_exists = generated_file.is_file()

        self.assertEqual(restored, len(DEFAULT_GENERATED_SECTIONS) + 1)
        self.assertEqual(restored_from_cache, restored)
        self.assertTrue(generated_exists)
        self.assertEqual(len(cached), 1)

    def test_restore_rejects_a_download_with_the_wrong_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot, release = _published_snapshot(root)
            for asset in release.iterdir():
                asset.write_bytes(b"tampered")

            with self.assertRaisesRegex(SiteError, "manifest expects"):
                restore_generated_wiki_snapshot(
                    root, snapshot, download_url=release.as_uri()
                )
            cache_entries = list((root / ".romwiki" / "snapshot-cache").iterdir())

        self.assertEqual(cache_entries, [])

    def test_restore_reports_an_unavailable_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot, release = _published_snapshot(root)
            for asset in release.iterdir():
                asset.unlink()

            with self.assertRaisesRegex(SiteError, "Could not download"):
                restore_generated_wiki_snapshot(
                    root, snapshot, download_url=release.as_uri()
                )

    def test_restore_prefers_a_matching_local_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            count = create_generated_wiki_snapshot(root, snapshot)

            restored = restore_generated_wiki_snapshot(
                root, snapshot, download_url=(root / "absent").as_uri()
            )

        self.assertEqual(restored, count)

    def test_publish_uploads_only_missing_assets_without_clobbering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            asset = _manifest_entry(snapshot)["asset"]
            runner = _FakeGh(release_exists=False)

            uploaded = publish_generated_wiki_snapshot(
                snapshot, repository="owner/repo", runner=runner
            )
            runner.assets.add(asset)
            uploaded_again = publish_generated_wiki_snapshot(
                snapshot, repository="owner/repo", runner=runner
            )

        self.assertEqual(uploaded, (asset,))
        self.assertEqual(uploaded_again, ())
        actions = [command[1:3] for command in runner.commands]
        self.assertEqual(
            actions,
            [
                ("release", "view"),
                ("release", "create"),
                ("release", "upload"),
                ("release", "view"),
            ],
        )
        upload = runner.commands[2]
        self.assertEqual(upload[3:5], ("snapshots", runner.uploaded[0]))
        self.assertEqual(Path(runner.uploaded[0]).name, asset)
        self.assertNotIn("--clobber", upload)
        self.assertIn("owner/repo", upload)

    def test_publish_rejects_an_archive_that_does_not_match_the_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            (snapshot / "test-game.tar.gz").write_bytes(b"different")
            runner = _FakeGh(release_exists=True)

            with self.assertRaisesRegex(SiteError, "does not match the manifest"):
                publish_generated_wiki_snapshot(snapshot, runner=runner)

        self.assertEqual(runner.commands, [])

    def test_site_source_fingerprint_covers_shared_engine_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            registry = root / "src" / "romwiki" / "engines" / "registry.py"
            registry.parent.mkdir(parents=True)
            registry.write_text("VALUE = 1\n", encoding="utf-8")
            catalog = SiteCatalog.load(root)
            site = catalog.get("test-game")
            original = _site_source_fingerprint(catalog, site)
            registry.write_text("VALUE = 2\n", encoding="utf-8")
            updated = _site_source_fingerprint(catalog, site)

        self.assertNotEqual(updated, original)

    def test_site_source_fingerprint_detects_a_same_timestamp_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            registry = root / "src" / "romwiki" / "engines" / "registry.py"
            registry.parent.mkdir(parents=True)
            registry.write_text("VALUE = 1\n", encoding="utf-8")
            catalog = SiteCatalog.load(root)
            site = catalog.get("test-game")
            original = _site_source_fingerprint(catalog, site)
            timestamp = registry.stat().st_mtime_ns
            registry.write_text("VALUE = 2\n", encoding="utf-8")
            os.utime(registry, ns=(timestamp, timestamp))
            updated = _site_source_fingerprint(catalog, site)

        self.assertNotEqual(updated, original)

    def test_site_source_fingerprint_frames_path_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            package = root / "src" / "romwiki"
            package.mkdir(parents=True)
            catalog = SiteCatalog.load(root)
            site = catalog.get("test-game")
            # Unframed, both layouts would hash "...a.pyXsrc/romwiki/b.pyY".
            (package / "a.py").write_text("X", encoding="utf-8")
            (package / "b.py").write_text("Y", encoding="utf-8")
            first = _site_source_fingerprint(catalog, site)
            (package / "b.py").unlink()
            (package / "a.py").write_text("Xsrc/romwiki/b.pyY", encoding="utf-8")
            second = _site_source_fingerprint(catalog, site)

        self.assertNotEqual(first, second)


class _FakeGh:
    def __init__(self, *, release_exists: bool) -> None:
        self.release_exists = release_exists
        self.assets: set[str] = set()
        self.commands: list[tuple[str, ...]] = []
        self.uploaded: list[str] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.commands.append(command)
        action = command[2]
        if action == "view" and not self.release_exists:
            return subprocess.CompletedProcess(command, 1, "", "release not found")
        if action == "view":
            stdout = json.dumps({"assets": [{"name": name} for name in self.assets]})
            return subprocess.CompletedProcess(command, 0, stdout, "")
        if action == "create":
            self.release_exists = True
        if action == "upload":
            staged = [value for value in command[4:] if value.endswith(".tar.gz")]
            self.uploaded.extend(staged)
            self.assets.update(Path(value).name for value in staged)
        return subprocess.CompletedProcess(command, 0, "", "")


def _manifest_entry(snapshot: Path) -> dict[str, object]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    entry: dict[str, object] = manifest["sites"]["test-game"]
    return entry


def _published_snapshot(root: Path) -> tuple[Path, Path]:
    """Create a snapshot whose archive exists only in a local "release"."""
    snapshot = root / "snapshot"
    create_generated_wiki_snapshot(root, snapshot)
    entry = _manifest_entry(snapshot)
    release = root / "release"
    release.mkdir()
    archive = snapshot / str(entry["archive"])
    asset = snapshot_asset_name("test-game", str(entry["archive_sha256"]))
    archive.replace(release / asset)
    return snapshot, release


def _make_site(
    root: Path,
    *,
    sections: tuple[str, ...] = DEFAULT_GENERATED_SECTIONS,
) -> Path:
    """Create a catalog with one published game and its generated downloads.

    Returns the path of the site's Pokémon download.
    """
    portal = root / "sites" / "portal"
    game = root / "sites" / "games" / "test-game"
    portal.mkdir(parents=True)
    game.mkdir(parents=True)
    (portal / "site.toml").write_text(
        """
[site]
id = "portal"
name = "Portal"
kind = "portal"
slug = ""
published = true
order = 0
[appearance]
theme = "portal"
""".strip(),
        encoding="utf-8",
    )
    (game / "game.toml").write_text(
        """
[site]
id = "test-game"
name = "Test Game"
kind = "game"
slug = "test-game"
published = true
order = 1
[game]
profile = "test-game"
generation = 1
base_game = "test-game"
platform = "nintendo-ds"
platform_name = "Nintendo DS"
creator = "Tester"
generated_sections = [{generated_sections}]
[appearance]
theme = "platinum"
""".format(
            generated_sections=", ".join(f'"{section}"' for section in sections)
        ).strip(),
        encoding="utf-8",
    )
    for section in sections:
        write_public_dataset(
            game / "wiki",
            section,
            {
                "schema_version": 1,
                "dataset": section,
                "game": "test-game",
                "record_count": 0,
                "records": [],
            },
        )
    return game / "wiki" / "data" / "pokemon.json.gz"
