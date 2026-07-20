from __future__ import annotations

from html import escape
from typing import Any


def type_badges(types: list[dict[str, Any]]) -> str:
    badges = []
    seen = set()
    for value in types:
        name = str(value["name"])
        if name in seen:
            continue
        seen.add(name)
        label = display_name(name)
        badges.append(
            f'<span class="rw-type rw-type--{escape(name)}">{escape(label)}</span>'
        )
    return '<span class="rw-type-list">' + "".join(badges) + "</span>"


def stat_list(stats: dict[str, int]) -> list[str]:
    fields = (
        ("HP", "hp"),
        ("Attack", "attack"),
        ("Defense", "defense"),
        ("Sp. Atk", "special_attack"),
        ("Sp. Def", "special_defense"),
        ("Speed", "speed"),
    )
    lines = ['<div class="rw-stat-list" aria-label="Base stats">']
    for label, key in fields:
        value = stats[key]
        percentage = min(value, 255) / 255 * 100
        lines.append(
            '<div class="rw-stat">'
            f"<span>{label}</span>"
            f'<span class="rw-stat__value">{value}</span>'
            f'<span class="rw-stat__track" aria-hidden="true"><span class="rw-stat__bar" style="--stat-percent:{percentage:.2f}%"></span></span>'
            "</div>"
        )
    lines.append("</div>")
    return lines


def pokemon_summary(record: dict[str, Any]) -> list[str]:
    sprite = record.get("sprite")
    if sprite:
        media = (
            f'<img data-rw-sprite src="{escape(sprite["url"], quote=True)}" '
            f'alt="{escape(record["name"], quote=True)} sprite" loading="lazy" '
            'referrerpolicy="no-referrer">'
            '<span class="rw-summary__placeholder" hidden>Sprite unavailable</span>'
        )
        attribution = (
            f'<a href="{escape(sprite["source_url"], quote=True)}">'
            f'{escape(sprite["source"])}</a>'
        )
    else:
        media = '<span class="rw-summary__placeholder">Sprite unavailable</span>'
        attribution = "Not available"
    ability_links = []
    for value in record["abilities"]:
        if value["name"] is None:
            continue
        slug = value.get("slug")
        label = escape(value["name"])
        ability_links.append(
            f'<a href="../../abilities/{escape(slug, quote=True)}/">{label}</a>'
            if slug
            else label
        )
    abilities = ", ".join(dict.fromkeys(ability_links)) or "None"
    dex = record["national_dex_id"]
    dex_label = f"#{dex:03}" if dex is not None else "—"
    return [
        '<section class="rw-summary">',
        f'<div class="rw-summary__media">{media}</div>',
        '<div class="rw-summary__body">',
        type_badges(record["types"]),
        '<dl class="rw-summary__facts">',
        f"<div><dt>National Pokédex</dt><dd>{dex_label}</dd></div>",
        f"<div><dt>Abilities</dt><dd>{abilities}</dd></div>",
        f"<div><dt>Base stat total</dt><dd>{sum(record['base_stats'].values())}</dd></div>",
        f"<div><dt>Sprite source</dt><dd>{attribution}</dd></div>",
        "</dl>",
        "</div>",
        "</section>",
        "",
    ]


def display_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))
