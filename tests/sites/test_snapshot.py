from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from romwiki.sites.data_exports import write_public_dataset
from romwiki.sites.snapshot import (
    REQUIRED_WIKI_SECTIONS,
    SNAPSHOT_MANIFEST,
    SNAPSHOT_SCHEMA_VERSION,
    _source_fingerprint,
    create_generated_wiki_snapshot,
    restore_generated_wiki_snapshot,
)
from romwiki.util.errors import SiteError


class GeneratedWikiSnapshotTests(unittest.TestCase):
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
theme = "documentation"
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


def _make_site(root: Path) -> Path:
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
[appearance]
theme = "test-game"
""".strip(),
        encoding="utf-8",
    )
    first = None
    for section in REQUIRED_WIKI_SECTIONS:
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
