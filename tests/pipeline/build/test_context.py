from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from romwiki.pipeline.build.context import GameBuildContext
from romwiki.pipeline.transforms.comparisons import compare_datasets
from romwiki.schema.versions import (
    ENCOUNTERS_RAW_SCHEMA_VERSION,
    ITEMS_RAW_SCHEMA_VERSION,
    MOVES_RAW_SCHEMA_VERSION,
)


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


def _extractor(
    calls: list, schema_version: int = MOVES_RAW_SCHEMA_VERSION
) -> Callable[[Any], dict]:
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

    def test_a_corrupted_cache_file_is_a_miss_that_self_heals(self) -> None:
        valid = _extractor([])(_result("hash-a"))
        wrong_envelope = {**valid, "engine": 4}
        mismatched_records = {**valid, "record_count": 2, "records": [{}]}
        corruptions = {
            "list": json.dumps([valid]),
            "truncated": json.dumps(valid)[:-10],
            "wrong envelope": json.dumps(wrong_envelope),
            "mismatched records": json.dumps(mismatched_records),
        }
        for name, content in corruptions.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                calls: list = []
                extractor = _extractor(calls)
                cache_root = Path(directory)
                _context(cache_root)._raw("moves/raw", extractor)
                path = cache_root / "moves" / "raw.json"
                path.write_text(content, encoding="utf-8")

                with self.assertLogs("romwiki", level="WARNING") as logs:
                    value = _context(cache_root)._raw("moves/raw", extractor)
                _context(cache_root)._raw("moves/raw", extractor)

                self.assertEqual(len(calls), 2)
                self.assertEqual(value["value"], 2)
                self.assertIn("Ignoring", "\n".join(logs.output))
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["value"], 2
                )


class GameBuildContextCanonicalFormTests(unittest.TestCase):
    def test_fresh_and_cached_extractions_have_one_in_memory_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            fresh = _context(cache_root, refresh=True)._raw(
                "encounters/raw", _encounter_extractor(walking_rate=10)
            )
            cached = _context(cache_root)._raw("encounters/raw", _unreachable)
        uncached = GameBuildContext(_result("hash-a"), Mock())._raw(
            "encounters/raw", _encounter_extractor(walking_rate=10)
        )

        for value in (fresh, uncached):
            self.assertEqual(json.dumps(value), json.dumps(cached))
        self.assertEqual(fresh["records"][0]["encounter_form_rates"], [0, 0, 0, 0, 0])
        self.assertEqual(
            list(cached["records"][0]),
            [
                "area_id",
                "locations",
                "walking",
                "encounter_form_rates",
                "slots_by_level",
                "active",
            ],
        )
        self.assertEqual(fresh["records"][0]["slots_by_level"], {"5": 25})

    def test_comparisons_do_not_depend_on_which_side_was_cached(self) -> None:
        def compare(cache_root: Path, *, refresh: bool) -> str:
            current = _context(cache_root / "current", refresh=refresh)._raw(
                "encounters/raw", _encounter_extractor(walking_rate=20)
            )
            baseline = _context(cache_root / "baseline", refresh=refresh)._raw(
                "encounters/raw", _encounter_extractor(walking_rate=10)
            )
            return json.dumps(compare_datasets(current, baseline))

        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            fresh = compare(cache_root, refresh=True)
            cached = compare(cache_root, refresh=False)

        self.assertEqual(fresh, cached)
        self.assertEqual(json.loads(fresh)["counts"]["changed"], 1)


def _encounter_extractor(walking_rate: int) -> Callable[[Any], dict]:
    def extract(result) -> dict:
        return {
            "schema_version": ENCOUNTERS_RAW_SCHEMA_VERSION,
            "game": "test-profile",
            "engine": "gen4_platinum",
            "dataset": "wild_encounters",
            "source": {"rom_sha256": result.image.hashes.sha256},
            "record_count": 1,
            "records": [
                {
                    "area_id": 1,
                    "locations": [{"header_id": 3, "name": "Route 201"}],
                    "walking": {"slots": (), "rate": walking_rate},
                    "encounter_form_rates": (0, 0, 0, 0, 0),
                    "slots_by_level": {5: 25},
                    "active": True,
                }
            ],
        }

    return extract


def _unreachable(result) -> dict:
    raise AssertionError("expected a cache hit")


if __name__ == "__main__":
    unittest.main()
