from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from romwiki.renderers.mkdocs.catalog import _SKELETON_FILTER_COUNTS, write_text

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CATALOG_CONFIG_JS = (
    REPOSITORY_ROOT / "sites/shared/overrides/assets/javascripts/catalog/config.js"
)
_CATALOG_BLOCK = re.compile(r"^  (\w+): \{\n(.*?)\n  \},", re.MULTILINE | re.DOTALL)


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


class SkeletonFilterCountsTests(unittest.TestCase):
    """Guards `_SKELETON_FILTER_COUNTS` against drifting from the interactive
    catalog's actual filter/range configuration in `catalog/config.js`.
    """

    def test_matches_the_javascript_catalog_configuration(self) -> None:
        text = CATALOG_CONFIG_JS.read_text(encoding="utf-8")
        expected = {}
        for kind, body in _CATALOG_BLOCK.findall(text):
            filter_count = range_count = 0
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("filters:"):
                    filter_count = stripped.count("{ key:")
                elif stripped.startswith("ranges:"):
                    range_count = stripped.count("{ key:")
            # search box (1) + filters (plus the injected change-status
            # filter) + two fields per range + sort-by (1) + direction (1).
            expected[kind] = 1 + (filter_count + 1) + range_count * 2 + 1 + 1

        self.assertEqual(_SKELETON_FILTER_COUNTS, expected)


class CatalogPresentationTests(unittest.TestCase):
    def test_list_labels_match_detail_page_terminology(self) -> None:
        text = CATALOG_CONFIG_JS.read_text(encoding="utf-8")

        self.assertIn('["Base price", (record)', text)
        self.assertIn('["Fling power", (record)', text)
        self.assertIn('"Always hits"', text)
        self.assertIn('["Map header", locationIdentifier]', text)
        self.assertIn('sorts: [["label", "Area"]', text)
        self.assertIn('{ key: "obtainability", label: "Obtainability" }', text)
        self.assertIn('["Availability", pokemonAvailability]', text)

    def test_encounter_ranges_collapse_equal_levels(self) -> None:
        text = CATALOG_CONFIG_JS.read_text(encoding="utf-8")

        self.assertIn("record.min_level === record.max_level", text)


if __name__ == "__main__":
    unittest.main()
