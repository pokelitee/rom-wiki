from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs import render_item_pages

HOSTILE_NAME = "<img src=x onerror=alert(1)> {: onclick=alert(1) }"


class ItemRenderingTests(unittest.TestCase):
    def test_renders_heading_mechanics_navigation_and_catalog(self) -> None:
        page, index, catalog = _render(
            [
                _item(234, "leftovers", "Leftovers"),
                _item(235, "big-root", "Big Root"),
            ],
            "leftovers",
        )

        self.assertTrue(page.startswith("# Leftovers\n"))
        self.assertIn("## Mechanics", page)
        self.assertIn("<dt>Held effect ID</dt><dd>69</dd>", page)
        self.assertIn('href="../big-root/"', page)
        self.assertIn("<summary>Data provenance</summary>", page)
        self.assertIn("[#234 Leftovers](leftovers.md)", index)
        self.assertEqual(catalog["kind"], "items")
        self.assertEqual(
            [record["label"] for record in catalog["records"]],
            ["Leftovers", "Big Root"],
        )
        self.assertEqual(catalog["records"][0]["url"], "leftovers/")
        self.assertEqual(catalog["records"][0]["price"], 4000)

    def test_links_resolved_locations_from_page_and_catalog(self) -> None:
        record = {
            **_item(234, "leftovers", "Leftovers"),
            "locations": [
                {
                    "header_id": 7,
                    "name": "Route 201",
                    "kind": "visible",
                    "x": 12,
                    "z": 30,
                }
            ],
        }
        page, _, catalog = _render([record], "leftovers")

        self.assertIn("## Overworld locations", page)
        self.assertIn("[Route 201](../locations/header-007.md)", page)
        self.assertIn("| Visible | (12, 30) |", page)
        self.assertEqual(catalog["records"][0]["locations"], ["Route 201"])
        self.assertEqual(
            catalog["records"][0]["location_refs"],
            [
                {
                    "kind": "location",
                    "id": 7,
                    "label": "Route 201",
                    "url": "../locations/header-007/",
                }
            ],
        )

    def test_escapes_rom_name_in_heading(self) -> None:
        page, _, catalog = _render([_item(234, "leftovers", HOSTILE_NAME)], "leftovers")

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
        render_item_pages({"records": records}, output)
        page = (output / f"{slug}.md").read_text(encoding="utf-8")
        index = (output / "index.md").read_text(encoding="utf-8")
        catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
    return page, index, catalog


def _item(item_id: int, slug: str, name: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "data_archive_member": item_id,
        "name": name,
        "slug": slug,
        "public": True,
        "price": 4000,
        "hold_effect_id": 69,
        "pluck_effect_id": 0,
        "fling_effect_id": 0,
        "fling_power": 10,
        "berry": None,
        "reference": None,
        "wild_held_by": [],
        "trainer_held_by": [],
        "trainer_battle_items": [],
        "trainer_rewards": [],
        "locations": [],
        "shops": [],
        "gifts": [],
        "trades": [],
        "evolutions": [],
        "revives_into": None,
        "revives_at": [],
        "provenance": {"source": "rom", "archive": "itemdata.narc", "member": item_id},
    }


if __name__ == "__main__":
    unittest.main()
