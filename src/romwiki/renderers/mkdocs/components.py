from __future__ import annotations

from collections.abc import Callable, Mapping
from html import escape
from typing import Any

from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    escape_markdown,
    resolved_reference,
)

DISPLAY_NAMES = {
    "poke-balls": "Poké Balls",
    "poke-radar": "Poké Radar",
    "tm-hm": "TM / HM",
    "vs-recorder": "Vs. Recorder",
    "vs-seeker": "Vs. Seeker",
    "trainer-ai-item": "Trainer AI item",
}

def empty_state(message: str) -> list[str]:
    return [message, ""]


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def escape_table_cell(value: str) -> str:
    """Escape free-text ROM data for a raw Markdown table cell.

    Markdown tables split on ``|``, which HTML-escaping alone doesn't
    neutralize, so this is the shared escaping every table cell holding
    unstructured ROM/reference text (nicknames, OT names, etc.) should use.
    """
    return escape(value).replace("|", "&#124;")


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


def class_badge(damage_class: dict[str, Any]) -> str:
    name = str(damage_class["name"])
    label = display_name(name)
    return f'<span class="rw-class rw-class--{escape(name)}">{escape(label)}</span>'


def evolution_condition(entry: dict[str, Any], source_url: str) -> str:
    method = entry["method"]["name"]
    parameter = entry["parameter_data"]
    value = parameter.get("value") if parameter is not None else None
    raw_name = parameter.get("name", "") if parameter is not None else ""
    name = (
        raw_name.replace("-", " ").title()
        if raw_name.islower()
        else raw_name
    )
    parameter_label = escape(name)
    parameter_kind = parameter.get("kind") if parameter is not None else None
    if parameter_kind is None:
        if method in {
            "trade-held-item",
            "use-item",
            "use-item-male",
            "use-item-female",
            "level-held-item-day",
            "level-held-item-night",
        }:
            parameter_kind = "item"
        elif method == "level-knowing-move":
            parameter_kind = "move"
        elif method == "level-with-party-species":
            parameter_kind = "pokemon"
    parameter_id = parameter.get("id", value) if parameter is not None else None
    if parameter_kind in {"item", "move", "pokemon"} and parameter_id is not None:
        route_key = parameter.get("slug")
        if route_key is None and parameter_kind == "move":
            route_key = raw_name
        parameter_label = ROUTES.html_link(
            entity_reference(parameter_kind, parameter_id, name, route_key), source_url
        )
    conditions = {
        "friendship": "High friendship",
        "friendship-day": "High friendship during the day",
        "friendship-night": "High friendship at night",
        "level": f"Level {value}",
        "trade": "Trade",
        "trade-held-item": f"Trade while holding {parameter_label}",
        "use-item": f"Use {parameter_label}",
        "level-attack-greater": f"Level {value} with Attack > Defense",
        "level-attack-equal": f"Level {value} with Attack = Defense",
        "level-defense-greater": f"Level {value} with Attack < Defense",
        "level-personality-low": f"Level {value} (random — low personality value)",
        "level-personality-high": f"Level {value} (random — high personality value)",
        "level-ninjask": f"Level {value} (Ninjask branch)",
        "level-shedinja": f"Level {value} (Shedinja branch)",
        "beauty": f"Beauty {value}",
        "use-item-male": f"Use {parameter_label} (male)",
        "use-item-female": f"Use {parameter_label} (female)",
        "level-held-item-day": f"Level up during the day while holding {parameter_label}",
        "level-held-item-night": f"Level up at night while holding {parameter_label}",
        "level-knowing-move": f"Level up knowing {parameter_label}",
        "level-with-party-species": f"Level up with {parameter_label} in the party",
        "level-male": f"Level {value} (male)",
        "level-female": f"Level {value} (female)",
        "level-magnetic-field": "Level up in a magnetic field",
        "level-moss-rock": "Level up near a Moss Rock",
        "level-ice-rock": "Level up near an Ice Rock",
    }
    return conditions.get(method, f"{method.replace('-', ' ').title()} ({value})")


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


def summary_hero(
    media_html: str,
    fact_lines: list[str],
    *,
    genus: str | None = None,
    badges_html: str | None = None,
) -> list[str]:
    """The shared `<section class="rw-summary">` hero shell every record
    kind's page-top summary uses: a media slot, an optional genus line and
    badge row, and a facts `<dl>`. Callers build their own media/badges/facts
    HTML and pass it in rather than duplicating this shell.
    """
    return [
        '<section class="rw-summary">',
        f'<div class="rw-summary__media">{media_html}</div>',
        '<div class="rw-summary__body">',
        *(f'<p class="rw-summary__genus">{escape(genus)}</p>' for _ in [0] if genus),
        *(f'<div class="rw-summary__badges">{badges_html}</div>' for _ in [0] if badges_html),
        '<dl class="rw-summary__facts">',
        *fact_lines,
        "</dl>",
        "</div>",
        "</section>",
        "",
    ]


def pokemon_summary(record: dict[str, Any]) -> list[str]:
    portrait = record.get("portrait") or record.get("sprite")
    if portrait:
        media = (
            f'<img data-rw-sprite src="{escape(portrait["url"], quote=True)}" '
            f'alt="{escape(record["name"], quote=True)} sprite" loading="lazy" '
            'referrerpolicy="no-referrer">'
            '<span class="rw-summary__placeholder" hidden>Sprite unavailable</span>'
        )
    else:
        media = '<span class="rw-summary__placeholder">Sprite unavailable</span>'
    cry = record.get("cry")
    cry_html = ""
    if cry:
        cry_html = (
            f'<audio class="rw-summary__cry" controls preload="none" '
            f'src="{escape(cry["url"], quote=True)}">'
            "Your browser does not support audio playback."
            "</audio>"
        )
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
    classification = "".join(
        f'<span class="rw-summary__tag">{label}</span>'
        for flag, label in (
            ("is_legendary", "Legendary"),
            ("is_mythical", "Mythical"),
            ("is_baby", "Baby"),
        )
        if reference.get(flag)
    )
    body_color = (record.get("body_color") or {}).get("name")
    habitat = reference.get("habitat")
    shape = reference.get("shape")
    badges = type_badges(record["types"]) + classification
    fact_lines = [
        f"<div><dt>National Pokédex</dt><dd>{dex_label}</dd></div>",
        *(f"<div><dt>Form</dt><dd>{escape(display_name(form))}</dd></div>" for _ in [0] if form),
        *(f"<div><dt>Body color</dt><dd>{escape(display_name(body_color))}</dd></div>" for _ in [0] if body_color),
        f"<div><dt>Abilities</dt><dd>{abilities}</dd></div>",
        "<div><dt>Base stat total</dt><dd>"
        f"{summary_section_link(sum(record['base_stats'].values()), 'base-stats')}"
        "</dd></div>",
        *(f"<div><dt>Habitat</dt><dd>{escape(display_name(habitat))}</dd></div>" for _ in [0] if habitat),
        *(f"<div><dt>Shape</dt><dd>{escape(display_name(shape))}</dd></div>" for _ in [0] if shape),
        *(f"<div><dt>Height</dt><dd>{escape(measurements['height'])}</dd></div>" for _ in [0] if measurements.get("height")),
        *(f"<div><dt>Weight</dt><dd>{escape(measurements['weight'])}</dd></div>" for _ in [0] if measurements.get("weight")),
    ]
    return summary_hero(
        f"{media}{cry_html}", fact_lines, genus=genus, badges_html=badges
    )


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


def table_sprite_cell(sprite: dict[str, Any] | str | None) -> str:
    url = sprite if isinstance(sprite, str) else sprite.get("url") if sprite else None
    if not url:
        return '<span class="rw-table-sprite rw-table-sprite--empty" aria-hidden="true">—</span>'
    return (
        f'<img class="rw-table-sprite" src="{escape(url, quote=True)}" '
        'alt="" loading="lazy" referrerpolicy="no-referrer">'
    )


def sprite_with_link(sprite_html: str, link_html: str) -> str:
    return f'<span class="rw-cell-media">{sprite_html}{link_html}</span>'


def pokemon_table(header_lines: list[str], row_lines: list[str]) -> list[str]:
    return [*header_lines, *row_lines, ""]


def machine_link(
    machine: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    as_html: bool = False,
) -> str:
    item_id = machine.get("item_id")
    if item_id is None:
        name = str(machine["name"])
        return escape(name) if as_html else escape_markdown(name)
    reference = resolved_reference("item", item_id, machine["name"], index=references)
    if as_html:
        return ROUTES.html_link(reference, source_file)
    return ROUTES.markdown_link(reference, source_file)


def summary_section(class_name: str, fact_lines: list[str]) -> list[str]:
    return [
        f'<section class="{class_name}">',
        '<dl class="rw-summary__facts">',
        *fact_lines,
        "</dl>",
        "</section>",
        "",
    ]


def fact_grid(
    facts: tuple[tuple[str, str], ...],
    *,
    class_name: str = "rw-data-grid",
    escape_values: bool = True,
) -> list[str]:
    lines = [f'<dl class="{class_name}">']
    for name, value in facts:
        rendered_value = escape(value) if escape_values else value
        lines.append(f"<div><dt>{escape(name)}</dt><dd>{rendered_value}</dd></div>")
    lines.append("</dl>")
    return lines


def summary_section_link(value: str | int, anchor: str) -> str:
    return f'<a href="#{escape(anchor, quote=True)}">{escape(str(value))}</a>'


def record_nav_link(
    href: str | None,
    label: str,
    direction: str,
    sprite_url: str | None = None,
) -> str:
    if href is None:
        return escape(label)
    sprite_html = (
        f'<img class="rw-record-nav__sprite" src="{escape(sprite_url, quote=True)}" '
        'alt="" loading="lazy" referrerpolicy="no-referrer">'
        if sprite_url
        else ""
    )
    return (
        f'<a class="rw-record-nav__link rw-record-nav__link--{direction}" '
        f'href="{escape(href, quote=True)}">'
        f"{sprite_html}"
        f'<span class="rw-record-nav__label">{escape(label)}</span>'
        "</a>"
    )


def record_navigation(
    previous_link: str | None,
    following_link: str | None,
    aria_label: str,
) -> list[str]:
    if previous_link is None and following_link is None:
        return []
    return [
        f'<nav class="rw-record-nav" aria-label="{escape(aria_label)}">',
        previous_link or "<span></span>",
        following_link or "<span></span>",
        "</nav>",
        "",
    ]


def record_navigation_for(
    kind: str,
    source_url: str,
    previous: Mapping[str, Any] | None,
    following: Mapping[str, Any] | None,
    *,
    aria_label: str,
    identity: Callable[[Mapping[str, Any]], int | str],
    route_key: Callable[[Mapping[str, Any]], int | str | None],
    label: Callable[[Mapping[str, Any]], str],
    sprite_url: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> list[str]:
    """Build the previous/next footer navigation for one record kind."""

    def link(record: Mapping[str, Any], text: str, direction: str) -> str:
        href = ROUTES.published_href(
            entity_reference(kind, identity(record), text, route_key(record)),
            source_url,
        )
        sprite = sprite_url(record) if sprite_url is not None else None
        return record_nav_link(href, text, direction, sprite)

    previous_link = (
        link(previous, f"← {label(previous)}", "prev")
        if previous is not None
        else None
    )
    following_link = (
        link(following, f"{label(following)} →", "next")
        if following is not None
        else None
    )
    return record_navigation(previous_link, following_link, aria_label)


def reference_sprite_cell(
    kind: str,
    identifier: int | str | None,
    references: ReferenceIndex | None,
) -> str:
    """Render a table sprite cell resolved through the reference index."""
    url = (
        references.sprite_url(kind, identifier)
        if references is not None and identifier is not None
        else None
    )
    return table_sprite_cell(url)


def reference_type_cell(
    kind: str,
    identifier: int | str | None,
    references: ReferenceIndex | None,
) -> str:
    """Render a table type-badges cell resolved through the reference index."""
    types = (
        references.types(kind, identifier)
        if references is not None and identifier is not None
        else None
    )
    return type_badges(list(types)) if types else "—"


def reference_description(record: dict[str, Any], empty_message: str) -> list[str]:
    reference = record.get("reference") or {}
    short_effect = reference.get("short_effect")
    effect = reference.get("effect")
    flavor_text = reference.get("flavor_text")
    lines: list[str] = []
    if short_effect or effect:
        lines.extend(["## Effect", ""])
        if short_effect:
            lines.append(f'<p><strong>{escape(" ".join(short_effect.split()))}</strong></p>')
        if effect and effect != short_effect:
            lines.append(f'<p>{escape(" ".join(effect.split()))}</p>')
        lines.append("")
    if flavor_text:
        version_label = (
            f"{display_name(reference['version'])} Pokédex"
            if reference.get("version")
            else "Pokédex"
        )
        lines.extend(pokedex_quote(flavor_text, version_label))
    if not lines:
        lines = empty_state(empty_message)
    return lines


def pokedex_quote(text: str, version_label: str) -> list[str]:
    return [
        '<figure class="rw-pokedex-entry">',
        f"<blockquote>{escape(' '.join(text.split()))}</blockquote>",
        f"<figcaption>{escape(version_label)}</figcaption>",
        "</figure>",
        "",
    ]


def reference_source_link(record: dict[str, Any]) -> list[str]:
    reference = record.get("reference") or {}
    source_url = reference.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        return []
    source_name = reference.get("source") or "PokéDB / PokéAPI"
    return [f"[View the {escape_markdown(source_name)} source record]({source_url})."]


def provenance_section(
    body: list[str], *, summary: str = "Data provenance"
) -> list[str]:
    return [
        '<details class="rw-source-details" markdown="1">',
        f"<summary>{escape(summary)}</summary>",
        "",
        *body,
        "",
        "</details>",
        "",
    ]


def provenance_fact_table(fields: tuple[tuple[str, str], ...]) -> list[str]:
    """Render the shared "Native field | Value" table used across every
    Data provenance section that has ROM-native engine values not already
    shown elsewhere on the page.
    """
    return [
        "| Native field | Value |",
        "| ------------ | ----- |",
        *(f"| {label} | {value} |" for label, value in fields),
        "",
    ]


def rom_record_source(
    archive: str, member: int | str, *, label: str = "Source"
) -> str:
    """The shared "<Label>: exact ROM record from `archive` member `id`."
    sentence every Data provenance section uses to cite its source record.

    Kept bare on purpose — no parameter for appending explanatory text, so
    every kind's Source line stays the same short shape. Explanation or
    caveats belong in their own following sentence, not folded into this one.
    """
    return f"{label}: exact ROM record from `{archive}` member `{member}`."


def name_table_source(label: str, archive: str, member: int) -> str:
    """The shared "<Label> name source: ROM message table ..." sentence."""
    return f"{label} name source: ROM message table `{archive}` member `{member}`."


def shop_price(price: int | None, currency: str) -> str:
    if price is None:
        return "—"
    if currency == "money":
        return f"₽{price:,}"
    return f"{price:,} {currency.upper()}"


def badge_requirement(badges: int | None) -> str:
    if badges is None:
        return "Always"
    if badges == 0:
        return "Start"
    return f"{badges} badge" if badges == 1 else f"{badges} badges"


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
