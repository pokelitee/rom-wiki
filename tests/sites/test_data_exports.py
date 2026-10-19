from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from romwiki.sites.data_exports import (
    prune_public_datasets,
    validate_public_data,
    write_public_comparison,
    write_public_dataset,
)
from romwiki.util.errors import SiteError


class PublicDataExportTests(unittest.TestCase):
    def test_dataset_updates_preserve_separate_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = {
                "schema_version": 1,
                "game": "test-game",
                "dataset": "moves",
                "records": [],
            }
            comparison = {
                "schema_version": 1,
                "game": "test-game",
                "kind": "moves",
                "records": [],
            }
            write_public_dataset(root, "moves", dataset)
            write_public_comparison(root, "moves", comparison)
            write_public_dataset(root, "moves", dataset)
            self.assertTrue((root / "data/comparisons/moves.json").is_file())
            self.assertEqual(len(validate_public_data(root)), 1)
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [entry["path"] for entry in manifest["files"]], ["moves.json.gz"]
            )
            write_public_comparison(root, "moves", None)
            self.assertFalse((root / "data/comparisons/moves.json").exists())

    def test_writes_deterministic_dataset_and_manifest(self) -> None:
        dataset = {
            "schema_version": 3,
            "game": "test-game",
            "dataset": "pokemon",
            "record_count": 1,
            "records": [{"name": "Bulbasaur", "id": 1}],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_public_dataset(root, "pokemon", dataset)
            archive = root / "data/pokemon.json.gz"
            first = archive.read_bytes()
            write_public_dataset(root, "pokemon", dataset)

            self.assertEqual(archive.read_bytes(), first)
            with gzip.open(archive, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), dataset)
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["game"], "test-game")
        self.assertEqual(manifest["files"][0]["record_count"], 1)
        self.assertEqual(
            manifest["files"][0]["sha256"],
            hashlib.sha256(first).hexdigest(),
        )

    def test_does_not_publish_comparison_exports(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "dataset": "moves",
            "record_count": 0,
            "records": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_public_dataset(root, "moves", dataset)

            self.assertFalse((root / "data/comparisons").exists())
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                all(
                    not entry["path"].startswith("comparisons/")
                    for entry in manifest["files"]
                )
            )

    def test_removes_stale_comparison_export_directory(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "dataset": "moves",
            "record_count": 0,
            "records": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale_dir = root / "data/comparisons"
            stale_dir.mkdir(parents=True)
            (stale_dir / "moves.json.gz").write_bytes(b"stale")

            write_public_dataset(root, "moves", dataset)

            self.assertFalse(stale_dir.exists())

    def test_complete_build_prunes_disabled_dataset_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("pokemon", "trainers", "locations"):
                write_public_dataset(
                    root,
                    kind,
                    {
                        "schema_version": 1,
                        "game": "test-game",
                        "dataset": kind,
                        "record_count": 0,
                        "records": [],
                    },
                )

            prune_public_datasets(
                root,
                {"pokemon"},
                "test-game",
            )
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["pokemon.json.gz"],
        )

    def test_incremental_manifest_matches_one_described_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, extra in (
                ("pokemon", {"record_count": 2}),
                ("trainers", {"kind": "trainer_battles"}),
                ("moves", {}),
            ):
                write_public_dataset(
                    root,
                    kind,
                    {
                        "schema_version": 4,
                        "game": "test-game",
                        "dataset": kind,
                        "records": [{"id": 1}, {"id": 2}],
                        **extra,
                    },
                )
            manifest_path = root / "data/manifest.json"
            incremental = manifest_path.read_bytes()

            manifest_path.unlink()
            prune_public_datasets(root, {"pokemon", "trainers", "moves"}, "test-game")

            self.assertEqual(manifest_path.read_bytes(), incremental)

    def test_writing_one_dataset_does_not_reread_other_archives(self) -> None:
        def dataset(kind: str) -> dict[str, object]:
            return {
                "schema_version": 1,
                "game": "test-game",
                "dataset": kind,
                "record_count": 0,
                "records": [],
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_public_dataset(root, "pokemon", dataset("pokemon"))
            with patch(
                "romwiki.sites.data_exports.gzip.decompress",
                side_effect=AssertionError("archive was decompressed"),
            ):
                write_public_dataset(root, "moves", dataset("moves"))
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["moves.json.gz", "pokemon.json.gz"],
        )

    def test_archive_with_unchanged_size_and_mtime_is_rehashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("moves", "pokemon"):
                write_public_dataset(
                    root,
                    kind,
                    {
                        "schema_version": 1,
                        "game": "test-game",
                        "dataset": kind,
                        "record_count": 0,
                        "records": [],
                    },
                )
            archive = root / "data/pokemon.json.gz"
            original = archive.read_bytes()
            original_stat = archive.stat()
            source = gzip.decompress(original)
            replacement = next(
                candidate
                for digit in b"123456789"
                if len(
                    candidate := gzip.compress(
                        source.replace(
                            b'"record_count":0', b'"record_count":%c' % digit
                        ),
                        mtime=0,
                    )
                )
                == len(original)
            )
            self.assertNotEqual(replacement, original)
            archive.write_bytes(replacement)
            os.utime(archive, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            self.assertEqual(archive.stat().st_size, original_stat.st_size)
            self.assertEqual(archive.stat().st_mtime_ns, original_stat.st_mtime_ns)

            prune_public_datasets(root, {"moves", "pokemon"}, "test-game")
            manifest = json.loads(
                (root / "data/manifest.json").read_text(encoding="utf-8")
            )
            validate_public_data(root)

        pokemon = manifest["files"][1]
        self.assertNotEqual(pokemon["record_count"], 0)
        self.assertEqual(pokemon["sha256"], hashlib.sha256(replacement).hexdigest())

    def test_validation_rejects_a_modified_archive(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "dataset": "moves",
            "record_count": 0,
            "records": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_public_dataset(root, "moves", dataset)
            manifest_path = root / "data/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "checksum mismatch"):
                validate_public_data(root)
