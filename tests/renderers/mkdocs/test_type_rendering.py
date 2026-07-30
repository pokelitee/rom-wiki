from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.type_charts import build_type_dataset
from romwiki.profiles.loader import ProfileRepository
from romwiki.renderers.mkdocs.types import render_type_chart


class TypeChartRenderingTests(unittest.TestCase):
    def test_renders_one_semantic_matrix_page_with_type_badges(self) -> None:
        profile = next(
            profile
            for profile in ProfileRepository.load(Path("profiles")).profiles
            if profile.id == "renegade-platinum"
        )
        dataset = build_type_dataset(profile)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_type_chart(dataset, output)
            page = (output / "index.md").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("# Type effectiveness", page)
        self.assertIn("<table>", page)
        self.assertIn(
            '<caption class="rw-visually-hidden">'
            "Type effectiveness by attacking and defending type"
            "</caption>",
            page,
        )
        self.assertIn('<th scope="col">', page)
        self.assertIn('<th scope="row">', page)
        self.assertEqual(page.count("rw-type--fairy"), 2)
        self.assertIn(">Fairy</span>", page)
        self.assertNotIn("](#", page)
        self.assertNotIn('<span id="', page)
        self.assertNotIn("| Fairy |", page)
        self.assertIn("rw-effectiveness--effective", page)
        self.assertIn("rw-effectiveness--resisted", page)
        self.assertIn("rw-effectiveness--neutral", page)
        self.assertIn("rw-effectiveness--immune", page)
        self.assertIn('aria-label="Super effective: 2×"', page)
        self.assertIn('aria-label="Normal effectiveness: —"', page)
        self.assertIn("<strong>0×</strong>", page)
        self.assertIn('class="rw-type-chart__legend"', page)
        self.assertIn('class="rw-type-chart__axis"', page)
        self.assertIn('aria-label="Attacking by row, defending by column"', page)
        self.assertIn("Atk ↓ / Def →</span>", page)


if __name__ == "__main__":
    unittest.main()
