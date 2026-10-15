from __future__ import annotations

import re
import unittest

import markdown

from romwiki.renderers.mkdocs.components import (
    MarkdownColumn,
    content_tabs,
    markdown_section,
    markdown_table_from_cells,
    provenance_fact_table,
    provenance_section,
)
from romwiki.renderers.mkdocs.html import (
    count_markdown_tab_sets,
    html_code,
    html_content_tabs,
    html_details,
    html_paragraph,
    html_provenance_fact_table,
    html_provenance_section,
    html_table,
)

# Mirrors the Markdown extensions in `sites/shared/mkdocs.base.yml` that
# affect generated detail-page bodies.
_EXTENSIONS = (
    "attr_list",
    "md_in_html",
    "tables",
    "admonition",
    "pymdownx.details",
    "pymdownx.tabbed",
    "toc",
)
_EXTENSION_CONFIGS = {
    "pymdownx.tabbed": {"alternate_style": True},
    "toc": {"permalink": True},
}


def _convert(lines: list[str]) -> tuple[str, list[dict[str, object]]]:
    converter = markdown.Markdown(
        extensions=list(_EXTENSIONS), extension_configs=_EXTENSION_CONFIGS
    )
    html = converter.convert("\n".join(lines))
    return html, converter.toc_tokens


def _normalized(html: str) -> str:
    html = re.sub(r"\s*/>", ">", html)
    return re.sub(r">\s+<", "><", html).strip()


class HtmlBuilderParityTests(unittest.TestCase):
    """Raw-HTML builders must render exactly like their Markdown twins."""

    def assert_same_rendering(self, markdown_lines: list[str], html_lines: list[str]):
        expected, expected_toc = _convert(markdown_lines)
        actual, actual_toc = _convert(html_lines)
        self.assertEqual(_normalized(actual), _normalized(expected))
        self.assertEqual(actual_toc, expected_toc)

    def test_table_matches_markdown_table(self) -> None:
        columns = (MarkdownColumn("Location"), MarkdownColumn("Level", "right"))
        self.assert_same_rendering(
            markdown_table_from_cells(
                columns,
                [("[Route 201](route.md)", "5"), ("`header-001`", "7")],
            ),
            html_table(
                columns,
                [
                    ('<a href="route.md">Route 201</a>', "5"),
                    (html_code("header-001"), "7"),
                ],
            ),
        )

    def test_table_rejects_mismatched_rows(self) -> None:
        with self.assertRaises(ValueError):
            html_table((MarkdownColumn("A"),), [("1", "2")])

    def test_sections_keep_markdown_headings_in_the_toc(self) -> None:
        columns = (MarkdownColumn("Item"),)
        self.assert_same_rendering(
            [
                *markdown_section(
                    "Items",
                    ["Intro text.", "", *markdown_table_from_cells(columns, [("A",)])],
                ),
                *markdown_section("Locations", ["None.", ""]),
            ],
            [
                *markdown_section(
                    "Items",
                    [*html_paragraph("Intro text."), *html_table(columns, [("A",)])],
                ),
                *markdown_section("Locations", html_paragraph("None.")),
            ],
        )

    def test_content_tabs_match_pymdownx_tabbed(self) -> None:
        self.assert_same_rendering(
            [
                "## Party",
                "",
                *content_tabs([("Snivy", ["First."]), ("Tepig & co", ["Second."])]),
            ],
            [
                "## Party",
                "",
                *html_content_tabs(
                    [
                        ("Snivy", html_paragraph("First.")),
                        ("Tepig & co", html_paragraph("Second.")),
                    ],
                    set_index=1,
                ),
            ],
        )

    def test_content_tabs_keep_raw_block_bodies_unwrapped(self) -> None:
        html, _toc = _convert(
            html_content_tabs(
                [("A", ['<section class="x">', "<p>*kept*</p>", "</section>", ""])],
                set_index=3,
            )
        )

        self.assertIn('data-tabs="3:1"', html)
        self.assertIn('id="__tabbed_3_1"', html)
        self.assertIn('<div class="tabbed-block">\n<section class="x">', html)
        self.assertIn("<p>*kept*</p>", html)

    def test_details_match_md_in_html_details(self) -> None:
        columns = (MarkdownColumn("Trainer"),)
        self.assert_same_rendering(
            [
                '<details markdown="1">',
                "<summary>6 other parties</summary>",
                "",
                *markdown_table_from_cells(columns, [("Sam",)]),
                "</details>",
                "",
            ],
            html_details("6 other parties", html_table(columns, [("Sam",)])),
        )

    def test_provenance_section_matches_markdown_version(self) -> None:
        self.assert_same_rendering(
            provenance_section(
                [
                    *provenance_fact_table([("Class ID", "`5`")]),
                    "Source: exact record from `trdata.narc`.",
                ]
            ),
            html_provenance_section(
                [
                    *html_provenance_fact_table([("Class ID", html_code(5))]),
                    f"<p>Source: exact record from {html_code('trdata.narc')}.</p>",
                ]
            ),
        )


class MarkdownTabSetCountTests(unittest.TestCase):
    def test_counts_sibling_labels_as_one_set(self) -> None:
        lines = content_tabs([("A", ["a"]), ("B", ["b"])])

        self.assertEqual(count_markdown_tab_sets(lines), 1)

    def test_counts_separated_and_nested_sets(self) -> None:
        nested = content_tabs([("Inner", ["x"])])
        lines = [
            *content_tabs([("A", nested), ("B", ["b"])]),
            "Between.",
            "",
            *content_tabs([("C", ["c"])]),
        ]

        self.assertEqual(count_markdown_tab_sets(lines), 3)

    def test_ignores_pages_without_tabs(self) -> None:
        self.assertEqual(count_markdown_tab_sets(["## Party", "", "Text."]), 0)


if __name__ == "__main__":
    unittest.main()
