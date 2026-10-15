"""Trainer party cards: identity, battle attributes, stats, and moves."""

from __future__ import annotations

from html import escape
from typing import Any

from romwiki.renderers.mkdocs.components import (
    ability_link,
    class_badge,
    display_name,
    type_badges,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
)


def party_cards(
    party: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None = None,
) -> list[str]:
    lines = ['<div class="rw-party-grid">']
    for index, member in enumerate(party, start=1):
        lines.extend(_party_card(index, member, source_url, references))
    lines.extend(["</div>", ""])
    return lines


def _party_card(
    index: int,
    member: dict[str, Any],
    source_url: str,
    references: ReferenceIndex | None,
) -> list[str]:
    pokemon = member["pokemon"]
    pokemon_identifier = pokemon.get("id", pokemon["slug"])
    pokemon_reference = (
        references.resolve_matching("pokemon", pokemon_identifier, pokemon["name"])
        if references is not None
        else entity_reference(
            "pokemon",
            pokemon_identifier,
            pokemon["name"],
            pokemon.get("page_slug", pokemon.get("slug")),
        )
    )
    pokemon_link = ROUTES.html_link(pokemon_reference, source_url)
    pokemon_sprite = pokemon.get("sprite")
    sprite_icon = (
        f'<img class="rw-party-card__sprite" src="{escape(pokemon_sprite["url"], quote=True)}" '
        f'alt="" width="48" height="48" loading="lazy">'
        if pokemon_sprite and pokemon_sprite.get("url")
        else ""
    )
    pokemon_types = pokemon.get("types", [])
    types_html = (
        f'<div class="rw-party-card__types">{type_badges(pokemon_types)}</div>'
        if pokemon_types
        else ""
    )
    card = [
        '<article class="rw-party-card">',
        f'<span class="rw-party-card__slot">Slot {index}</span>',
        '<div class="rw-party-card__header">',
        sprite_icon,
        '<div class="rw-party-card__identity">',
        '<div class="rw-party-card__heading">',
        f'<span class="rw-party-card__level">Lv. {member["level"]}</span>',
        f"<h3>{pokemon_link}</h3>",
        _party_gender(member.get("gender")),
        "</div>",
        types_html,
        "</div>",
        "</div>",
        '<dl class="rw-party-card__details rw-party-card__section">',
        *[
            f"<div><dt>{label}</dt><dd>{value}</dd></div>"
            for label, value in _party_details(member, source_url)
        ],
        "</dl>",
    ]
    stat_table = _party_stat_table(member)
    if stat_table:
        card.extend(
            [
                '<section class="rw-party-card__section">',
                '<h4 class="rw-party-card__section-title">Stats</h4>',
                *stat_table,
                "</section>",
            ]
        )
    card.extend(_party_moves(member, source_url))
    card.append("</article>")
    return [line for line in card if line]


def _party_details(member: dict[str, Any], source_url: str) -> list[tuple[str, str]]:
    details = []
    nature = member.get("nature")
    if nature:
        nature_name = nature.get("name", nature.get("value"))
        if nature_name is not None:
            details.append(("Nature", escape(str(nature_name))))
    ability_link_html = _party_ability(member.get("ability"), source_url)
    if ability_link_html is not None:
        details.append(("Ability", ability_link_html))
    details.append(("Held item", _held_item(member["held_item"], source_url)))
    return details


def _held_item(held_item: dict[str, Any] | None, source_url: str) -> str:
    if not held_item or not held_item["name"]:
        return "—"
    item_link = ROUTES.html_link(
        entity_reference(
            "item",
            held_item.get("id", held_item.get("slug", held_item["name"])),
            held_item["name"],
            held_item.get("slug"),
        ),
        source_url,
    )
    item_sprite = held_item.get("sprite_url")
    item_icon = (
        f'<img class="rw-party-card__item-icon" src="{escape(item_sprite, quote=True)}" '
        'alt="" width="21" height="21" loading="lazy">'
        if item_sprite
        else ""
    )
    return f'<span class="rw-party-card__item">{item_icon}{item_link}</span>'


def _party_moves(member: dict[str, Any], source_url: str) -> list[str]:
    moves_heading = "Moves"
    if member["moves_source"] == "level-up" and member["moves"]:
        moves_heading += (
            '<abbr class="rw-inline-note" title="Derived from the Pokémon\'s '
            'level-up learnset at this level.">*</abbr>'
        )
    lines = [
        '<section class="rw-party-card__section">',
        f'<h4 class="rw-party-card__section-title">{moves_heading}</h4>',
    ]
    if member["moves_source"] == "explicit" or member["moves"]:
        move_label = escape(f"{member['pokemon']['name']} moves", quote=True)
        lines.append(f'<ol class="rw-party-card__moves" aria-label="{move_label}">')
        for move_index, move in enumerate(member["moves"], start=1):
            lines.append(_party_move(move_index, move, source_url))
        if not member["moves"]:
            lines.append('<li class="rw-party-card__moves-empty">No moves</li>')
        lines.append("</ol>")
    elif member["moves_source"] == "level-up":
        lines.append(
            '<p class="rw-party-card__default-moves">Uses default level-up moves.</p>'
        )
    else:
        lines.append('<p class="rw-party-card__default-moves">Moves unavailable.</p>')
    lines.append("</section>")
    return lines


def _party_move(move_index: int, move: dict[str, Any], source_url: str) -> str:
    display_slug = move["name"]
    # `slug` (when present) is the move's real, ROM-derived page
    # slug -- see `pipeline/enrichment/trainers.py`'s own
    # comment -- distinct from `name`/`display_slug`, which is
    # PokeDB's canonical slug used only for display formatting.
    route_slug = move.get("slug", display_slug)
    move_link = ROUTES.html_link(
        entity_reference(
            "move",
            move.get("id", route_slug),
            display_name(display_slug),
            route_slug,
        ),
        source_url,
    )
    move_metadata = []
    if move.get("type"):
        move_metadata.append(type_badges([move["type"]]))
    if move.get("damage_class"):
        move_metadata.append(class_badge(move["damage_class"]))
    metadata_html = (
        '<span class="rw-party-card__move-meta">' + "".join(move_metadata) + "</span>"
        if move_metadata
        else ""
    )
    return (
        '<li><span class="rw-party-card__move-name">'
        f'<span aria-hidden="true">{move_index}. </span>{move_link}'
        f"</span>{metadata_html}</li>"
    )


def _party_ability(ability: dict[str, Any] | None, source_url: str) -> str | None:
    if not ability:
        return None
    if ability.get("name"):
        return ability_link(ability, source_url)
    possibilities = ability.get("possibilities")
    if not isinstance(possibilities, list) or not possibilities:
        return None
    links = [
        ability_link(possibility, source_url)
        for possibility in possibilities
        if isinstance(possibility, dict) and possibility.get("name")
    ]
    if not links:
        return None
    return " / ".join(links)


def _party_gender(gender: dict[str, Any] | None) -> str:
    if not gender:
        return ""
    name = gender.get("name", gender.get("value"))
    if name is None:
        return ""
    label = str(name)
    symbol, modifier = {
        "male": ("♂", "male"),
        "female": ("♀", "female"),
        "genderless": ("⚲", "genderless"),
    }.get(label.lower(), ("•", "unknown"))
    return (
        f'<span class="rw-party-card__gender rw-party-card__gender--{modifier}" '
        f'aria-label="{escape(label, quote=True)}" title="{escape(label, quote=True)}">'
        f"{symbol}</span>"
    )


# A nature's raised/lowered stat pair, keyed by name. This is a fixed game
# mechanic identical across every Generation III+ title, not ROM data, so it
# is safe to hardcode rather than decode per-ROM.
_NATURE_STAT_MODIFIERS: dict[str, tuple[str, str] | None] = {
    "Hardy": None,
    "Lonely": ("attack", "defense"),
    "Brave": ("attack", "speed"),
    "Adamant": ("attack", "special_attack"),
    "Naughty": ("attack", "special_defense"),
    "Bold": ("defense", "attack"),
    "Docile": None,
    "Relaxed": ("defense", "speed"),
    "Impish": ("defense", "special_attack"),
    "Lax": ("defense", "special_defense"),
    "Timid": ("speed", "attack"),
    "Hasty": ("speed", "defense"),
    "Serious": None,
    "Jolly": ("speed", "special_attack"),
    "Naive": ("speed", "special_defense"),
    "Modest": ("special_attack", "attack"),
    "Mild": ("special_attack", "defense"),
    "Quiet": ("special_attack", "speed"),
    "Bashful": None,
    "Rash": ("special_attack", "special_defense"),
    "Calm": ("special_defense", "attack"),
    "Gentle": ("special_defense", "defense"),
    "Sassy": ("special_defense", "speed"),
    "Careful": ("special_defense", "special_attack"),
    "Quirky": None,
}

# Row labels that reflect a nature-affected final stat, as opposed to raw
# IVs/EVs, which a nature does not modify.
_CALCULATED_STAT_LABELS = {"Value", "Min", "Max"}

_STAT_COLUMNS = (
    ("HP", "hp"),
    ("Atk", "attack"),
    ("Def", "defense"),
    ("SpA", "special_attack"),
    ("SpD", "special_defense"),
    ("Spe", "speed"),
)


def _nature_stat_modifiers(nature: dict[str, Any] | None) -> tuple[str, str] | None:
    name = (nature or {}).get("name")
    return _NATURE_STAT_MODIFIERS.get(name) if isinstance(name, str) else None


def _stat_cell(key: str, value: Any, modifiers: tuple[str, str] | None) -> str:
    css_class = ""
    if modifiers:
        boosted, lowered = modifiers
        if key == boosted:
            css_class = ' class="rw-party-card__stat--up"'
        elif key == lowered:
            css_class = ' class="rw-party-card__stat--down"'
    return f"<td{css_class}>{_stat_value(value)}</td>"


def _party_stat_table(member: dict[str, Any]) -> list[str]:
    rows: list[tuple[str, dict[str, Any]]] = []
    calculated = member.get("calculated_stats")
    calculated_values = calculated.get("values") if calculated else None
    ranged_stats: list[tuple[str, dict[str, Any]]] = []
    if isinstance(calculated_values, dict) and all(
        key in calculated_values for _, key in _STAT_COLUMNS
    ):
        if any(_is_stat_range(calculated_values[key]) for _, key in _STAT_COLUMNS):
            ranged_stats.extend(
                [
                    ("Min", _stat_bounds(calculated_values, "minimum")),
                    ("Max", _stat_bounds(calculated_values, "maximum")),
                ]
            )
        else:
            rows.append(("Value", calculated_values))
    for label, field in (("IV", "ivs"), ("EV", "evs")):
        attribute = member.get(field)
        values = attribute.get("values") if attribute else None
        if isinstance(values, dict) and all(key in values for _, key in _STAT_COLUMNS):
            rows.append((label, values))
    rows.extend(ranged_stats)
    if not rows:
        return []
    nature_modifiers = _nature_stat_modifiers(member.get("nature"))
    return [
        '<table class="rw-party-card__stats">',
        "<caption>Stats, IVs, and EVs</caption>",
        "<thead><tr><th></th>"
        + "".join(f'<th scope="col">{label}</th>' for label, _ in _STAT_COLUMNS)
        + "</tr></thead>",
        "<tbody>",
        *[
            f'<tr><th scope="row">{label}</th>'
            + "".join(
                _stat_cell(
                    key,
                    values[key],
                    nature_modifiers if label in _CALCULATED_STAT_LABELS else None,
                )
                for _, key in _STAT_COLUMNS
            )
            + "</tr>"
            for label, values in rows
        ],
        "</tbody>",
        "</table>",
    ]


def _is_stat_range(value: Any) -> bool:
    return isinstance(value, dict) and {"minimum", "maximum"}.issubset(value)


def _stat_bounds(values: dict[str, Any], bound: str) -> dict[str, Any]:
    return {
        key: value[bound] if _is_stat_range(value) else value
        for _, key in _STAT_COLUMNS
        for value in (values[key],)
    }


def _stat_value(value: Any) -> str:
    if _is_stat_range(value):
        return f"{value['minimum']}-{value['maximum']}"
    return str(value)
