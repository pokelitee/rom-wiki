from __future__ import annotations

from html import escape
from typing import Any

from romwiki.renderers.mkdocs.references import ROUTES, entity_reference


DISPLAY_NAMES = {
    "poke-balls": "Poké Balls",
    "poke-radar": "Poké Radar",
    "tm-hm": "TM / HM",
    "vs-recorder": "Vs. Recorder",
    "vs-seeker": "Vs. Seeker",
}


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


def stat_list(
    stats: dict[str, int], reference_stats: dict[str, int] | None = None
) -> list[str]:
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
        comparison = '<span class="rw-stat__delta" aria-hidden="true"></span>'
        if reference_stats is not None and key in reference_stats:
            difference = value - reference_stats[key]
            if difference:
                sign = "+" if difference > 0 else ""
                comparison = (
                    f'<span class="rw-stat__delta rw-stat__delta--'
                    f'{"up" if difference > 0 else "down"}" '
                    f'aria-label="{sign}{difference} from base game">'
                    f'{sign}{difference}</span>'
                )
        lines.append(
            '<div class="rw-stat">'
            f"<span>{label}</span>"
            f'<span class="rw-stat__value">{value}</span>'
            f"{comparison}"
            f'<span class="rw-stat__track" aria-hidden="true"><span class="rw-stat__bar" style="--stat-percent:{percentage:.2f}%"></span></span>'
            "</div>"
        )
    total = sum(stats.values())
    reference_total = sum(reference_stats.values()) if reference_stats else None
    total_comparison = ""
    if reference_total is not None and total != reference_total:
        difference = total - reference_total
        sign = "+" if difference > 0 else ""
        total_comparison = (
            f'<span class="rw-stat__delta rw-stat__delta--'
            f'{"up" if difference > 0 else "down"}">{sign}{difference}</span>'
        )
    else:
        total_comparison = '<span class="rw-stat__delta" aria-hidden="true"></span>'
    lines.append(
        '<div class="rw-stat rw-stat--total">'
        "<span>Total</span>"
        f'<span class="rw-stat__value">{total}</span>'
        f"{total_comparison}"
        '<span class="rw-stat__track" aria-hidden="true"></span>'
        "</div>"
    )
    lines.append("</div>")
    return lines


def pokemon_summary(record: dict[str, Any]) -> list[str]:
    portrait = record.get("portrait") or record.get("sprite")
    if portrait:
        media = (
            f'<img data-rw-sprite src="{escape(portrait["url"], quote=True)}" '
            f'alt="{escape(record["name"], quote=True)} sprite" loading="lazy" '
            'referrerpolicy="no-referrer">'
            '<span class="rw-summary__placeholder" hidden>Sprite unavailable</span>'
        )
        attribution = (
            f'<a href="{escape(portrait["source_url"], quote=True)}">'
            f'{escape(portrait["source"])}</a>'
        )
    else:
        media = '<span class="rw-summary__placeholder">Sprite unavailable</span>'
        attribution = "Not available"
    ability_links = []
    for value in record["abilities"]:
        if value["name"] is None:
            continue
        ability_links.append(
            ROUTES.html_link(
                entity_reference(
                    "ability",
                    value.get("id", value["name"]),
                    value["name"],
                    value.get("slug"),
                ),
                f"pokemon/{record['slug']}/",
            )
        )
    abilities = ", ".join(dict.fromkeys(ability_links)) or "None"
    dex = record["national_dex_id"]
    dex_label = f"#{dex:03}" if dex is not None else "—"
    reference = record.get("reference") or {}
    genus = reference.get("genus")
    form = record.get("form")
    measurements = _pokemon_measurements(reference)
    return [
        '<section class="rw-summary">',
        f'<div class="rw-summary__media">{media}</div>',
        '<div class="rw-summary__body">',
        *(f'<p class="rw-summary__genus">{escape(genus)}</p>' for _ in [0] if genus),
        type_badges(record["types"]),
        '<dl class="rw-summary__facts">',
        f"<div><dt>National Pokédex</dt><dd>{dex_label}</dd></div>",
        *(f"<div><dt>Form</dt><dd>{escape(display_name(form))}</dd></div>" for _ in [0] if form),
        f"<div><dt>Abilities</dt><dd>{abilities}</dd></div>",
        f"<div><dt>Base stat total</dt><dd>{sum(record['base_stats'].values())}</dd></div>",
        *(f"<div><dt>Height</dt><dd>{escape(measurements['height'])}</dd></div>" for _ in [0] if measurements.get("height")),
        *(f"<div><dt>Weight</dt><dd>{escape(measurements['weight'])}</dd></div>" for _ in [0] if measurements.get("weight")),
        "</dl>",
        "</div>",
        f'<p class="rw-summary__credit">Sprite: {attribution}</p>',
        "</section>",
        "",
    ]


def _pokemon_measurements(reference: dict[str, Any]) -> dict[str, str]:
    measurements = {}
    height = reference.get("height_dm")
    if isinstance(height, int):
        meters = height / 10
        total_inches = round(meters * 39.3701)
        measurements["height"] = (
            f"{meters:g} m ({total_inches // 12}′{total_inches % 12}″)"
        )
    weight = reference.get("weight_hg")
    if isinstance(weight, int):
        kilograms = weight / 10
        measurements["weight"] = f"{kilograms:g} kg ({kilograms * 2.20462:.1f} lb)"
    return measurements


def display_name(value: str) -> str:
    return DISPLAY_NAMES.get(
        value,
        " ".join(part.capitalize() for part in value.split("-")),
    )


def shard_cost(costs: dict[str, int]) -> str:
    return ", ".join(
        f"{amount} {color.title()}"
        for color, amount in costs.items()
        if amount
    ) or "Free"


def tutor_requirement(tutor: dict[str, Any]) -> str:
    if tutor.get("kind") == "special":
        return f"Friendship {tutor['minimum_friendship']}"
    return shard_cost(tutor["shard_costs"])
