from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from romwiki.sites.catalog import SiteCatalog
from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.snapshot import (
    DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
    REQUIRED_WIKI_SECTIONS,
    SNAPSHOT_MANIFEST,
    SNAPSHOT_SCHEMA_VERSION,
    _site_source_fingerprint,
    _source_fingerprint,
    _validate_site_archive_manifest,
    create_generated_wiki_snapshot,
    publish_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
    snapshot_asset_name,
)
from romwiki.util.errors import SiteError


class GeneratedWikiSnapshotTests(unittest.TestCase):
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

    def test_directory_restore_rejects_paths_outside_generated_sections(self) -> None:
        # The single-archive and per-site-directory restore paths share one
        # path-traversal validator; this proves the directory path actually
        # calls it too, not just the single-archive path covered by
        # test_restore_rejects_paths_outside_generated_sections above.
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
            stale = generated_file.parent / "stale.md"
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

    def test_snapshot_accepts_dev_pages_present_in_generated_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = _make_site(root).with_name("bulbasaur.md")
            page.write_text("# Bulbasaur", encoding="utf-8")
            _write_dev_pages(root, 'pokemon = ["bulbasaur"]')
            snapshot = root / "snapshot"

            count = create_generated_wiki_snapshot(root, snapshot)
            restored = restore_generated_wiki_snapshot(
                root, snapshot, site_ids=("test-game",)
            )

        self.assertEqual(restored, count)

    def test_snapshot_rejects_dev_pages_missing_from_generated_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            _write_dev_pages(root, 'pokemon = ["bulbasaur"]')

            with self.assertRaisesRegex(SiteError, "pokemon/bulbasaur.md"):
                create_generated_wiki_snapshot(root, root / "snapshot")

    def test_restore_rejects_dev_pages_missing_from_the_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            snapshot = root / "snapshot"
            create_generated_wiki_snapshot(root, snapshot)
            _write_dev_pages(root, 'pokemon = ["bulbasaur"]')

            with self.assertRaisesRegex(SiteError, "pokemon/bulbasaur.md"):
                restore_generated_wiki_snapshot(root, snapshot, site_ids=("test-game",))

    def test_type_chart_is_required_generated_content(self) -> None:
        self.assertIn("types", REQUIRED_WIKI_SECTIONS)

    def test_snapshot_is_deterministic_and_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"

            first_count = create_generated_wiki_snapshot(root, first)
            second_count = create_generated_wiki_snapshot(root, second)
            generated_file.unlink()
            restored_count = restore_generated_wiki_snapshot(root, first)

            self.assertEqual(first_count, len(REQUIRED_WIKI_SECTIONS) + 2)
            self.assertEqual(second_count, first_count)
            self.assertEqual(restored_count, first_count)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(generated_file.read_text(encoding="utf-8"), "# Pokémon")

    def test_snapshot_honors_declared_partial_generated_sections(self) -> None:
        sections = (
            "pokemon",
            "abilities",
            "moves",
            "items",
            "encounters",
            "types",
            "data",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root, sections=sections)
            archive_path = root / "partial.tar.gz"

            count = create_generated_wiki_snapshot(root, archive_path)
            with tarfile.open(archive_path, "r:gz") as archive:
                names = {member.name for member in archive}

        self.assertEqual(count, len(sections) + 2)
        self.assertFalse(any("/trainers/" in name for name in names))
        self.assertFalse(any("/locations/" in name for name in names))

    def test_restore_rejects_paths_outside_generated_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            archive_path = root / "unsafe.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                manifest = json.dumps(
                    {
                        "schema_version": SNAPSHOT_SCHEMA_VERSION,
                        "file_count": 1,
                        "source_fingerprint": _source_fingerprint(root),
                    }
                ).encode("utf-8")
                manifest_info = tarfile.TarInfo(SNAPSHOT_MANIFEST)
                manifest_info.size = len(manifest)
                archive.addfile(manifest_info, io.BytesIO(manifest))
                data = b"unsafe"
                info = tarfile.TarInfo("../unsafe.txt")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

            with self.assertRaisesRegex(SiteError, "invalid path"):
                restore_generated_wiki_snapshot(root, archive_path)

    def test_restore_rejects_snapshot_after_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            source = root / "src" / "romwiki" / "example.py"
            source.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            archive_path = root / "snapshot.tar.gz"
            create_generated_wiki_snapshot(root, archive_path)
            source.write_text("VALUE = 2\n", encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "snapshot is stale"):
                restore_generated_wiki_snapshot(root, archive_path)

    def test_source_fingerprint_is_independent_of_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src" / "romwiki" / "example.py"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"VALUE = 1\nOTHER = 2\n")
            lf_fingerprint = _source_fingerprint(root)
            source.write_bytes(b"VALUE = 1\r\nOTHER = 2\r\n")

            self.assertEqual(_source_fingerprint(root), lf_fingerprint)

    def test_source_fingerprint_ignores_publishing_only_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook = root / "src" / "romwiki" / "sites" / "mkdocs_hooks.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("VALUE = 1\n", encoding="utf-8")
            original = _source_fingerprint(root)
            hook.write_text("VALUE = 2\n", encoding="utf-8")

            self.assertEqual(_source_fingerprint(root), original)

    def test_snapshot_ignores_published_documentation_only_games(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_site(root)
            documentation = root / "sites" / "games" / "documentation"
            documentation.mkdir(parents=True)
            (documentation / "mkdocs.yml").write_text(
                "site_name: Documentation\n", encoding="utf-8"
            )
            (documentation / "game.toml").write_text(
                """
[site]
id = "documentation"
name = "Documentation"
kind = "game"
slug = "documentation"
published = true
order = 2
mkdocs_config = "mkdocs.yml"
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
            archive = root / "snapshot.tar.gz"

            count = create_generated_wiki_snapshot(root, archive)
            restored_count = restore_generated_wiki_snapshot(root, archive)

            self.assertEqual(count, len(REQUIRED_WIKI_SECTIONS) + 2)
            self.assertEqual(restored_count, count)

    def test_snapshot_rejects_markdown_targets_inside_raw_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated_file = _make_site(root)
            archive = root / "snapshot.tar.gz"
            create_generated_wiki_snapshot(root, archive)
            original_archive = archive.read_bytes()
            generated_file.write_text(
                '<a href="../../types/index.md#fire">Fire</a>',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                SiteError,
                "raw HTML must use a published URL",
            ):
                create_generated_wiki_snapshot(root, archive)

            self.assertEqual(archive.read_bytes(), original_archive)


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

        self.assertEqual(restored, len(REQUIRED_WIKI_SECTIONS) + 2)
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


def _write_dev_pages(root: Path, pages: str) -> None:
    (root / "sites" / "games" / "test-game" / "dev-pages.toml").write_text(
        f"[pages]\n{pages}\n", encoding="utf-8"
    )


def _make_site(
    root: Path,
    *,
    sections: tuple[str, ...] = REQUIRED_WIKI_SECTIONS,
) -> Path:
    portal = root / "sites" / "portal"
    game = root / "sites" / "games" / "test-game"
    portal.mkdir(parents=True)
    game.mkdir(parents=True)
    (portal / "mkdocs.yml").write_text("site_name: Portal\n", encoding="utf-8")
    (game / "mkdocs.yml").write_text("site_name: Game\n", encoding="utf-8")
    (portal / "site.toml").write_text(
        """
[site]
id = "portal"
name = "Portal"
kind = "portal"
slug = ""
published = true
order = 0
mkdocs_config = "mkdocs.yml"
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
mkdocs_config = "mkdocs.yml"
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
    first = None
    for section in sections:
        index = game / "wiki" / section / "index.md"
        index.parent.mkdir(parents=True)
        value = "# Pokémon" if first is None else f"# {section.title()}"
        index.write_text(value, encoding="utf-8")
        first = first or index
    assert first is not None
    write_public_dataset(
        game / "wiki",
        "pokemon",
        {
            "schema_version": 1,
            "dataset": "pokemon",
            "game": "test-game",
            "record_count": 0,
            "records": [],
        },
    )
    return first
