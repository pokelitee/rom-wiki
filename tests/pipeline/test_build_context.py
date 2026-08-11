from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest.mock import Mock

from romwiki.pipeline.build_context import GameBuildContext
from romwiki.schema.versions import ITEMS_RAW_SCHEMA_VERSION, MOVES_RAW_SCHEMA_VERSION


def _result(rom_sha256: str) -> Mock:
    result = Mock()
    result.match.profile.id = "test-profile"
    result.image.hashes.sha256 = rom_sha256
    return result


def _context(
    cache_root: Path,
    rom_sha256: str = "hash-a",
    *,
    refresh: bool = False,
    source_fingerprint: str | Mapping[str, str] = "source-a",
) -> GameBuildContext:
    return GameBuildContext(
        _result(rom_sha256),
        Mock(),
        cache_root=cache_root,
        refresh=refresh,
        source_fingerprint=source_fingerprint,
    )


def _extractor(calls: list, schema_version: int = MOVES_RAW_SCHEMA_VERSION) -> callable:
    def extract(result) -> dict:
        calls.append(result)
        return {
            "schema_version": schema_version,
            "game": "test-profile",
            "engine": "test-engine",
            "dataset": "moves",
            "record_count": 1,
            "source": {"rom_sha256": result.image.hashes.sha256},
            "value": len(calls),
        }

    return extract


class GameBuildContextCacheTests(unittest.TestCase):
    def test_reuses_a_cached_extraction_across_instances(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            with self.assertLogs("romwiki", level="DEBUG") as logs:
                first = _context(cache_root)
                first_value = first._raw("moves/raw", extractor)

                second = _context(cache_root)
                second_value = second._raw("moves/raw", extractor)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first_value, second_value)
        messages = "\n".join(logs.output)
        self.assertIn("Extraction cache miss for test-profile: moves/raw", messages)
        self.assertIn("Extraction cache hit for test-profile: moves/raw", messages)

    def test_a_changed_rom_hash_invalidates_the_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            _context(cache_root, "hash-a")._raw("moves/raw", extractor)
            _context(cache_root, "hash-b")._raw("moves/raw", extractor)

        self.assertEqual(len(calls), 2)

    def test_refresh_bypasses_a_valid_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            _context(cache_root)._raw("moves/raw", extractor)
            _context(cache_root, refresh=True)._raw("moves/raw", extractor)

        self.assertEqual(len(calls), 2)

    def test_changed_extraction_source_invalidates_the_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            _context(cache_root, source_fingerprint="source-a")._raw(
                "moves/raw", extractor
            )
            _context(cache_root, source_fingerprint="source-b")._raw(
                "moves/raw", extractor
            )

        self.assertEqual(len(calls), 2)

    def test_changed_extraction_source_invalidates_only_its_dataset(self) -> None:
        calls: list = []
        moves_extractor = _extractor(calls)
        items_extractor = _extractor(calls, ITEMS_RAW_SCHEMA_VERSION)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            first = _context(
                cache_root,
                source_fingerprint={"moves/raw": "moves-a", "items/raw": "items-a"},
            )
            first._raw("moves/raw", moves_extractor)
            first._raw("items/raw", items_extractor)

            second = _context(
                cache_root,
                source_fingerprint={"moves/raw": "moves-b", "items/raw": "items-a"},
            )
            second._raw("moves/raw", moves_extractor)
            second._raw("items/raw", items_extractor)

        self.assertEqual(len(calls), 3)

    def test_invalid_manifest_rebuilds_every_entry_in_the_context(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            initial = _context(cache_root)
            initial._raw("moves/raw", extractor)
            initial._raw("items/raw", extractor)
            manifest_path = cache_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cache_revision"] = 0
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            rebuilt = _context(cache_root)
            rebuilt._raw("moves/raw", extractor)
            rebuilt._raw("items/raw", extractor)

        self.assertEqual(len(calls), 4)

    def test_without_a_cache_root_every_call_re_extracts(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        context = GameBuildContext(_result("hash-a"), Mock())

        context._raw("moves/raw", extractor)
        context_two = GameBuildContext(_result("hash-a"), Mock())
        context_two._raw("moves/raw", extractor)

        self.assertEqual(len(calls), 2)

    def test_a_changed_dataset_schema_invalidates_only_that_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            _context(cache_root)._raw("moves/raw", extractor)
            path = cache_root / "moves" / "raw.json"
            cached = json.loads(path.read_text(encoding="utf-8"))
            cached["schema_version"] = 0
            path.write_text(json.dumps(cached), encoding="utf-8")

            _context(cache_root)._raw("moves/raw", extractor)

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
