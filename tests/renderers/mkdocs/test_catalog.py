from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.renderers.mkdocs.catalog import write_text


class WriteTextTests(unittest.TestCase):
    def test_writes_the_given_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"

            write_text(path, "# Hello\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "# Hello\n")

    def test_leaves_an_unchanged_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"
            write_text(path, "# Hello\n")
            original_mtime = path.stat().st_mtime_ns

            write_text(path, "# Hello\n")

            self.assertEqual(path.stat().st_mtime_ns, original_mtime)

    def test_rewrites_a_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"
            write_text(path, "# Hello\n")

            write_text(path, "# Goodbye\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "# Goodbye\n")


if __name__ == "__main__":
    unittest.main()
