from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.snapshot import (
    DIRECTORY_SNAPSHOT_SCHEMA_VERSION,
    REQUIRED_WIKI_SECTIONS,
    SNAPSHOT_MANIFEST,
    SNAPSHOT_SCHEMA_VERSION,
    _source_fingerprint,
    _validate_site_archive_manifest,
    create_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
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
                                "file_count": 1,
                                "archive_sha256": "digest",
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
        None,
    )
    return first
