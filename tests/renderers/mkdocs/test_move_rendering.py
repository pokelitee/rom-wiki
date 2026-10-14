from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from romwiki.pipeline.transforms.relationships import build_relationship_index
from romwiki.renderers.mkdocs import render_move_pages

HOSTILE_NAME = "<img src=x onerror=alert(1)> {: onclick=alert(1) }"


class MoveRenderingTests(unittest.TestCase):
    def test_renders_heading_summary_learners_and_catalog(self) -> None:
        page, index, catalog = _render(
            [
                {
                    **_move(85, "thunderbolt", "Thunderbolt"),
                    "machines": [{"name": "TM24"}],
                    "egg_move_pokemon": [{"slug": "pichu", "name": "Pichu"}],
                },
                _move(86, "thunder-wave", "Thunder Wave"),
            ],
            "thunderbolt",
        )

        self.assertTrue(page.startswith("# Thunderbolt\n"))
        self.assertIn("rw-type--electric", page)
        self.assertIn("<dt>Power</dt><dd>90</dd>", page)
        self.assertIn("<dt>Machine</dt><dd>TM24</dd>", page)
        self.assertIn("## Learned by", page)
        self.assertIn("### Egg moves", page)
        self.assertIn("[Pichu](../pokemon/pichu.md)", page)
        self.assertIn('href="../thunder-wave/"', page)
        self.assertIn("[Thunderbolt](thunderbolt.md)", index)
        self.assertEqual(catalog["kind"], "moves")
        self.assertEqual(catalog["records"][0]["url"], "thunderbolt/")
        self.assertEqual(
            catalog["records"][0]["access_methods"], ["machine", "egg move"]
        )
        self.assertEqual(catalog["records"][1]["access_methods"], ["no known learners"])

    def test_escapes_rom_name_in_heading(self) -> None:
        page, _, catalog = _render(
            [_move(85, "thunderbolt", HOSTILE_NAME)], "thunderbolt"
        )

        self.assertTrue(
            page.startswith(
                "# &lt;img src=x onerror=alert(1)&gt; \\{: onclick=alert(1) \\}\n"
            )
        )
        self.assertNotIn("<img src=x", page)
        self.assertEqual(catalog["records"][0]["label"], HOSTILE_NAME)


def _render(
    records: list[dict[str, Any]], slug: str
) -> tuple[str, str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        render_move_pages(
            {"records": records},
            output,
            relationships=build_relationship_index({}),
        )
        page = (output / f"{slug}.md").read_text(encoding="utf-8")
        index = (output / "index.md").read_text(encoding="utf-8")
        catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
    return page, index, catalog


def _move(move_id: int, slug: str, name: str) -> dict[str, Any]:
    return {
        "move_id": move_id,
        "slug": slug,
        "name": name,
        "public": True,
        "effect_id": 6,
        "damage_class_id": 1,
        "power": 90,
        "type_id": 13,
        "accuracy": 100,
        "pp": 15,
        "effect_chance": 10,
        "target_id": 0x10,
        "priority": 0,
        "flags": 0x12,
        "contest_effect_id": 17,
        "contest_type_id": 3,
        "type": {"id": 13, "name": "electric"},
        "damage_class": {"id": 1, "name": "special"},
        "machines": [],
        "tutors": [],
        "egg_move_pokemon": [],
        "provenance": {"source": "rom", "archive": "moves.narc", "member": move_id},
    }


if __name__ == "__main__":
    unittest.main()
