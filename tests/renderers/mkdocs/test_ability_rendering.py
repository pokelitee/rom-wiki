from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs import render_ability_pages

HOSTILE_NAME = "<img src=x onerror=alert(1)> {: onclick=alert(1) }"


class AbilityRenderingTests(unittest.TestCase):
    def test_renders_heading_pokemon_links_and_catalog(self) -> None:
        page, index, catalog = _render(
            [
                _ability(65, "overgrow", "Overgrow", [_bulbasaur(slots=[1])]),
                _ability(66, "blaze", "Blaze", []),
            ],
            "overgrow",
        )

        self.assertTrue(page.startswith("# Overgrow\n"))
        self.assertIn("[Bulbasaur](../pokemon/bulbasaur.md)", page)
        self.assertIn('href="../blaze/"', page)
        self.assertIn("[#065 Overgrow](overgrow.md)", index)
        self.assertIn("[#066 Blaze](blaze.md)", index)
        self.assertEqual(catalog["kind"], "abilities")
        self.assertEqual(
            [record["status"] for record in catalog["records"]],
            ["assigned", "unassigned"],
        )
        self.assertEqual(catalog["records"][0]["url"], "overgrow/")
        self.assertEqual(catalog["records"][0]["search_text"], "overgrow bulbasaur")

    def test_escapes_rom_name_in_heading(self) -> None:
        page, _, catalog = _render(
            [_ability(65, "overgrow", HOSTILE_NAME, [])], "overgrow"
        )

        self.assertTrue(
            page.startswith(
                "# &lt;img src=x onerror=alert(1)&gt; \\{: onclick=alert(1) \\}\n"
            )
        )
        self.assertNotIn("<img src=x", page)
        self.assertEqual(catalog["records"][0]["label"], HOSTILE_NAME)

    def test_escapes_rom_names_in_link_labels(self) -> None:
        pokemon = {**_bulbasaur(slots=[1]), "name": "<b>Bulba</b>"}
        page, index, _ = _render(
            [_ability(65, "overgrow", HOSTILE_NAME, [pokemon])], "overgrow"
        )

        self.assertIn(
            "[#065 &lt;img src=x onerror=alert(1)&gt; {: onclick=alert(1) }]"
            "(overgrow.md)",
            index,
        )
        self.assertNotIn("<img src=x", index)
        self.assertIn("[&lt;b&gt;Bulba&lt;/b&gt;](../pokemon/bulbasaur.md)", page)
        self.assertNotIn("<b>", page)


def _render(
    records: list[dict[str, Any]], slug: str
) -> tuple[str, str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        render_ability_pages({"records": records}, output)
        page = (output / f"{slug}.md").read_text(encoding="utf-8")
        index = (output / "index.md").read_text(encoding="utf-8")
        catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
    return page, index, catalog


def _ability(
    ability_id: int, slug: str, name: str, pokemon: list[dict[str, Any]]
) -> dict[str, Any]:
    return {"ability_id": ability_id, "slug": slug, "name": name, "pokemon": pokemon}


def _bulbasaur(*, slots: list[int]) -> dict[str, Any]:
    return {
        "member": 1,
        "national_dex_id": 1,
        "slug": "bulbasaur",
        "name": "Bulbasaur",
        "slots": slots,
    }


if __name__ == "__main__":
    unittest.main()
