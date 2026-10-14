from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from romwiki.util.json_io import (
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)


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

    def test_creates_missing_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "deeper" / "page.md"

            write_bytes_atomic(path, b"content")

            self.assertEqual(path.read_bytes(), b"content")

    def test_rewrites_same_size_content_that_differs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.bin"
            write_bytes_atomic(path, b"first")

            write_bytes_atomic(path, b"fifth")

            self.assertEqual(path.read_bytes(), b"fifth")

    def test_skips_reading_an_existing_file_whose_size_differs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.bin"
            write_bytes_atomic(path, b"first")

            with mock.patch.object(Path, "read_bytes") as read_bytes:
                write_bytes_atomic(path, b"longer content")

            read_bytes.assert_not_called()
            self.assertEqual(path.read_bytes(), b"longer content")

    def test_text_uses_lf_newlines_on_every_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"

            write_text_atomic(path, "# Title\n\nBody\n")

            self.assertEqual(path.read_bytes(), b"# Title\n\nBody\n")

    def test_text_rewrites_a_crlf_file_with_the_same_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"
            path.write_bytes(b"# Title\r\n")

            write_text_atomic(path, "# Title\n")

            self.assertEqual(path.read_bytes(), b"# Title\n")

    def test_writes_pretty_sorted_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"

            write_json_atomic(path, {"b": 1, "a": 2})

            self.assertEqual(path.read_bytes(), b'{\n  "a": 2,\n  "b": 1\n}\n')

    def test_writes_compact_json_on_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"

            write_json_atomic(path, {"b": [1, 2], "a": "é"}, compact=True)

            self.assertEqual(path.read_bytes(), '{"a":"é","b":[1,2]}\n'.encode())

    def test_writes_non_ascii_text_as_utf8_rather_than_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"

            write_json_atomic(path, {"name": "Pokémon ♂"})

            content = path.read_bytes()
            self.assertIn("Pokémon ♂".encode(), content)
            self.assertNotIn(b"\\u", content)
            self.assertEqual(json.loads(content.decode("utf-8")), {"name": "Pokémon ♂"})

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
