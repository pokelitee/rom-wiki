from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.type_charts import build_type_dataset
from romwiki.profiles.loader import ProfileRepository
from romwiki.renderers.mkdocs.types import render_type_chart


class TypeChartRenderingTests(unittest.TestCase):
    def test_renders_one_matrix_page_with_stable_type_anchors(self) -> None:
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
        self.assertIn("[Fairy](#fairy)", page)
        self.assertIn('<span id="fairy"></span>', page)
        self.assertIn("**0×**", page)
        self.assertIn('class="rw-type-chart__axis"', page)
        self.assertIn('aria-label="Attacking by row, defending by column"', page)
        self.assertIn("Atk ↓ / Def →</span>", page)


if __name__ == "__main__":
    unittest.main()
