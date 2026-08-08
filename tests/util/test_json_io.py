from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.util.json_io import write_bytes_atomic, write_json_atomic


class WriteJsonAtomicTests(unittest.TestCase):
    def test_writes_bytes_atomically_and_preserves_unchanged_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.bin"
            write_bytes_atomic(path, b"first")
            initial_mtime = path.stat().st_mtime_ns

            write_bytes_atomic(path, b"first")

            self.assertEqual(path.read_bytes(), b"first")
            self.assertEqual(path.stat().st_mtime_ns, initial_mtime)
            write_bytes_atomic(path, b"second")
            self.assertEqual(path.read_bytes(), b"second")
            self.assertFalse(path.with_suffix(".bin.tmp").exists())

    def test_writes_pretty_sorted_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"

            write_json_atomic(path, {"b": 1, "a": 2})

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n  "a": 2,\n  "b": 1\n}\n',
            )

    def test_leaves_an_unchanged_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            write_json_atomic(path, {"a": 1})
            original_mtime = path.stat().st_mtime_ns

            write_json_atomic(path, {"a": 1})

            self.assertEqual(path.stat().st_mtime_ns, original_mtime)

    def test_rewrites_a_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            write_json_atomic(path, {"a": 1})

            write_json_atomic(path, {"a": 2})

            self.assertIn('"a": 2', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
