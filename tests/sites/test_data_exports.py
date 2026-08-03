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
            write_public_dataset(root, "pokemon", dataset, None)
            archive = root / "data/pokemon.json.gz"
            first = archive.read_bytes()
            write_public_dataset(root, "pokemon", dataset, None)

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

    def test_removes_stale_comparison_export(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "dataset": "moves",
            "record_count": 0,
            "records": [],
        }
        comparison = {
            "schema_version": 1,
            "game": "test-game",
            "dataset": "moves_comparison",
            "kind": "moves",
            "record_count": 0,
            "records": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_public_dataset(root, "moves", dataset, comparison)
            comparison_path = root / "data/comparisons/moves.json.gz"
            self.assertTrue(comparison_path.is_file())

            write_public_dataset(root, "moves", dataset, None)

            self.assertFalse(comparison_path.exists())

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
                    None,
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
            write_public_dataset(root, "moves", dataset, None)
            manifest_path = root / "data/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(SiteError, "checksum mismatch"):
                validate_public_data(root)
