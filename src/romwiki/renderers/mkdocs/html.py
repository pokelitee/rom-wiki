"""Raw-HTML equivalents of the Markdown body builders in `components`.

Detail pages stay `.md` files so MkDocs keeps owning navigation, the page
table of contents, hooks, and templates, but their heavy bodies are emitted
as raw HTML blocks that Python-Markdown stashes instead of parsing. Each
builder reproduces the markup the configured extensions (`tables`,
`pymdownx.tabbed` alternate style, `md_in_html`) would have produced for the
equivalent Markdown.

Conventions every caller must keep:

- Headings stay Markdown (`markdown_section`). The `toc` extension only
  indexes headings it parses, so a raw `<h2>` would vanish from the page
  table of contents and lose its permalink.
- Every block starts at column 0 and is followed by a blank line; indented
  HTML is not recognised as a raw block and gets re-parsed as a paragraph.
- Cell and body content is HTML: escape text with `html.escape`, and link
  through `ROUTES.html_link`, which emits published directory URLs because
  MkDocs does not rewrite `.md` hrefs inside raw HTML.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from html import escape

from romwiki.renderers.mkdocs.components import MarkdownColumn


def html_code(value: object) -> str:
    return f"<code>{escape(str(value), quote=False)}</code>"


def html_paragraph(content_html: str) -> list[str]:
    return [f"<p>{content_html}</p>", ""]


def html_table(
    columns: Sequence[MarkdownColumn], rows: Iterable[Sequence[str]]
) -> list[str]:
    """Render already-formatted HTML cells as the `tables` extension would."""
    if not columns:
        raise ValueError("HTML tables require at least one column")
    openers = [
        ' style="text-align: right;"' if column.alignment == "right" else ""
        for column in columns
    ]
    lines = [
        "<table>",
        "<thead>",
        "<tr>"
        + "".join(
            f"<th{opener}>{escape(column.label, quote=False)}</th>"
            for column, opener in zip(columns, openers, strict=True)
        )
        + "</tr>",
        "</thead>",
        "<tbody>",
    ]
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(
                f"HTML table row has {len(row)} cells; expected {len(columns)}"
            )
        lines.append(
            "<tr>"
            + "".join(
                f"<td{opener}>{cell}</td>"
                for cell, opener in zip(row, openers, strict=True)
            )
            + "</tr>"
        )
    lines.extend(["</tbody>", "</table>", ""])
    return lines


def html_details(
    summary: str, body: Iterable[str], *, class_name: str | None = None
) -> list[str]:
    class_attribute = f' class="{escape(class_name)}"' if class_name else ""
    return [
        f"<details{class_attribute}>",
        f"<summary>{escape(summary)}</summary>",
        *(line for line in body if line),
        "</details>",
        "",
    ]


def html_provenance_section(
    body: Iterable[str], *, summary: str = "Data provenance"
) -> list[str]:
    """HTML twin of `components.provenance_section`."""
    return [
        "<hr>",
        "",
        *html_details(summary, body, class_name="rw-source-details"),
    ]


def html_provenance_fact_table(fields: Sequence[tuple[str, str]]) -> list[str]:
    """HTML twin of `components.provenance_fact_table`; values are HTML."""
    return html_table(
        (MarkdownColumn("Native field"), MarkdownColumn("Value")),
        ((escape(label, quote=False), value) for label, value in fields),
    )


def html_content_tabs(
    contents: Sequence[tuple[str, Sequence[str]]], *, set_index: int
) -> list[str]:
    """Render `pymdownx.tabbed` (alternate style) markup for HTML tab bodies.

    `set_index` must be unique on the page and disjoint from the tab sets
    `pymdownx.tabbed` numbers itself; see `count_markdown_tab_sets`.
    """
    if not contents:
        raise ValueError("Content tabs require at least one tab")
    name = f"__tabbed_{set_index}"
    checked = ' checked="checked"'
    inputs = "".join(
        f'<input{checked if number == 1 else ""} id="{name}_{number}" '
        f'name="{name}" type="radio">'
        for number in range(1, len(contents) + 1)
    )
    labels = "".join(
        f'<label for="{name}_{number}">{escape(label, quote=False)}</label>'
        for number, (label, _content) in enumerate(contents, start=1)
    )
    lines = [
        f'<div class="tabbed-set tabbed-alternate" '
        f'data-tabs="{set_index}:{len(contents)}">{inputs}'
        f'<div class="tabbed-labels">{labels}</div>',
        '<div class="tabbed-content">',
    ]
    for _label, content in contents:
        lines.append('<div class="tabbed-block">')
        lines.extend(line for line in content if line)
        lines.append("</div>")
    lines.extend(["</div>", "</div>", ""])
    return lines


_MARKDOWN_TAB_RE = re.compile(r'^( *)=== "')


def count_markdown_tab_sets(lines: Iterable[str]) -> int:
    """Count the tab sets `pymdownx.tabbed` will number in Markdown lines.

    Consecutive `=== "..."` labels at one indentation form a single set; a
    label nested inside a tab's indented body starts its own set.
    """
    count = 0
    last_was_tab: dict[int, bool] = {}
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        for deeper in [level for level in last_was_tab if level > indent]:
            del last_was_tab[deeper]
        is_tab = _MARKDOWN_TAB_RE.match(line) is not None
        if is_tab and not last_was_tab.get(indent, False):
            count += 1
        last_was_tab[indent] = is_tab
    return count
