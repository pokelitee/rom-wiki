from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from romwiki.pipeline.build_context import GameBuildContext


def _result(rom_sha256: str) -> Mock:
    result = Mock()
    result.match.profile.id = "test-profile"
    result.image.hashes.sha256 = rom_sha256
    return result


def _context(cache_root: Path, rom_sha256: str = "hash-a", *, refresh: bool = False) -> GameBuildContext:
    return GameBuildContext(
        _result(rom_sha256), Mock(), cache_root=cache_root, refresh=refresh
    )


def _extractor(calls: list) -> callable:
    def extract(result) -> dict:
        calls.append(result)
        return {
            "schema_version": 1,
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

            first = _context(cache_root)
            first_value = first._raw("kind/key", extractor)

            second = _context(cache_root)
            second_value = second._raw("kind/key", extractor)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first_value, second_value)

    def test_a_changed_rom_hash_invalidates_the_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            _context(cache_root, "hash-a")._raw("kind/key", extractor)
            _context(cache_root, "hash-b")._raw("kind/key", extractor)

        self.assertEqual(len(calls), 2)

    def test_refresh_bypasses_a_valid_cache(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            _context(cache_root)._raw("kind/key", extractor)
            _context(cache_root, refresh=True)._raw("kind/key", extractor)

        self.assertEqual(len(calls), 2)

    def test_without_a_cache_root_every_call_re_extracts(self) -> None:
        calls: list = []
        extractor = _extractor(calls)
        context = GameBuildContext(_result("hash-a"), Mock())

        context._raw("kind/key", extractor)
        context_two = GameBuildContext(_result("hash-a"), Mock())
        context_two._raw("kind/key", extractor)

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
