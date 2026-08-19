from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from romwiki.sites.data_exports import (
    prune_public_datasets,
    validate_public_data,
    write_public_dataset,
)
from romwiki.util.errors import SiteError


class PublicDataExportTests(unittest.TestCase):
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
