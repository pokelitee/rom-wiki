from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import write_text
from romwiki.renderers.mkdocs.components import display_name


def render_type_chart(dataset: dict[str, Any], output_root: Path) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    records = dataset["records"]
    headers = " | ".join(
        f"[{display_name(record['name'])}](#{record['name']})" for record in records
    )
    alignments = " | ".join("---:" for _ in records)
    lines = [
        "# Type effectiveness",
        "",
        "The attacking type is listed by row and the defending type by column. "
        "For dual-type Pokémon, multiply the two defending-type values.",
        "",
        "- **2×** — super effective",
        "- **½×** — not very effective",
        "- **0×** — no effect",
        "",
        '<div class="rw-type-chart" markdown="1">',
        "",
        '| <span class="rw-type-chart__axis" '
        'aria-label="Attacking by row, defending by column">'
        f"Atk ↓ / Def →</span> | {headers} |",
        f"| :------------------------ | {alignments} |",
    ]
    for record in records:
        values = " | ".join(
            _display_multiplier(matchup["multiplier"]) for matchup in record["matchups"]
        )
        name = record["name"]
        lines.append(
            f'| <span id="{escape(name)}"></span>**{display_name(name)}** | {values} |'
        )
    lines.extend(["", "</div>", ""])
    write_text(output_root / "index.md", "\n".join(lines))
    return 1


def _display_multiplier(multiplier: str) -> str:
    return {
        "0": "**0×**",
        "1/2": "½×",
        "1": "—",
        "2": "**2×**",
    }.get(multiplier, f"{multiplier}×")
