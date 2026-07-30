from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import write_text
from romwiki.renderers.mkdocs.components import (
    effectiveness_description,
    effectiveness_table_cell,
    effectiveness_value,
    type_badges,
)


def render_type_chart(dataset: dict[str, Any], output_root: Path) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    records = dataset["records"]
    lines = [
        "# Type effectiveness",
        "",
        "The attacking type is listed by row and the defending type by column. "
        "For dual-type Pokémon, multiply the two defending-type values.",
        "",
        '<ul class="rw-type-chart__legend" aria-label="Effectiveness legend">',
        _legend_item("2"),
        _legend_item("1/2"),
        _legend_item("0"),
        "</ul>",
        "",
        '<div class="rw-type-chart">',
        "<table>",
        '<caption class="rw-visually-hidden">'
        "Type effectiveness by attacking and defending type"
        "</caption>",
        "<thead>",
        "<tr>",
        '<th scope="col"><span class="rw-type-chart__axis" '
        'aria-label="Attacking by row, defending by column">'
        "Atk ↓ / Def →</span></th>",
    ]
    for record in records:
        lines.append(f'<th scope="col">{_type_badge(record["name"])}</th>')
    lines.extend(["</tr>", "</thead>", "<tbody>"])

    for record in records:
        lines.extend(
            [
                "<tr>",
                f'<th scope="row">{_type_badge(record["name"])}</th>',
                *(
                    effectiveness_table_cell(matchup["multiplier"])
                    for matchup in record["matchups"]
                ),
                "</tr>",
            ]
        )
    lines.extend(["</tbody>", "</table>", "</div>", ""])
    write_text(output_root / "index.md", "\n".join(lines))
    return 1


def _type_badge(name: str) -> str:
    return type_badges([{"name": name}])


def _legend_item(multiplier: str) -> str:
    return (
        "<li>"
        f"{effectiveness_value(multiplier)}"
        f"<span>{escape(effectiveness_description(multiplier).lower())}</span>"
        "</li>"
    )
