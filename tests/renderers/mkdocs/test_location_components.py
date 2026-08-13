from __future__ import annotations

import unittest

import markdown

from romwiki.renderers.mkdocs.location_components import append_warps


class LocationComponentContractTests(unittest.TestCase):
    def test_empty_warp_section_does_not_change_the_document(self) -> None:
        lines = ["# Location", ""]

        append_warps(lines, [], "locations/header-001.md")

        self.assertEqual(lines, ["# Location", ""])

    def test_dynamic_warp_table_has_stable_markdown_structure(self) -> None:
        lines: list[str] = []

        append_warps(
            lines,
            [
                {
                    "index": 0,
                    "x": 488,
                    "z": 824,
                    "destination_header_id": None,
                    "destination_warp_id": None,
                    "destination_name": None,
                    "destination_internal_name": None,
                    "destination_warp_exists": None,
                    "dynamic": True,
                }
            ],
            "locations/header-150.md",
        )

        self.assertEqual(
            lines,
            [
                "## Warps",
                "",
                "Dynamic destination means the ROM does not store one fixed "
                "destination header or destination warp for that row. The em "
                "dashes are explicit unavailable values, not missing cells.",
                "",
                "| Warp | Position | Destination | Destination map header | Destination warp |",
                "| ---: | -------- | ----------- | ---------------------- | ---------------: |",
                "| 0 | (488, 824) | Dynamic destination | — | — |",
                "",
            ],
        )
        rendered = markdown.markdown("\n".join(lines), extensions=["tables"])
        self.assertIn("<h2>Warps</h2>", rendered)
        self.assertIn("<table>", rendered)
        self.assertEqual(rendered.count("<td"), 5)


if __name__ == "__main__":
    unittest.main()
