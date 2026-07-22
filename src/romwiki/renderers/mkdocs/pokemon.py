from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text as _write_text,
)
from romwiki.renderers.mkdocs.components import (
    class_badge,
    evolution_condition,
    pokemon_summary,
    record_nav_link,
    record_navigation,
    stat_list,
    tutor_requirement,
    type_badges,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.references import ROUTES, ReferenceIndex, entity_reference


def render_pokemon_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    move_dataset: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    preevolutions = _index_preevolutions(public_records)
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{record['slug']}.md"
                for record in public_records
                if only_pages is None or record["slug"] in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    type_name_source = dataset.get("name_sources", {}).get("type_names")
    move_lookup = {
        record["move_id"]: record for record in (move_dataset or {}).get("records", [])
    }
    for index, record in enumerate(public_records):
        change = record_comparison(
            comparison, record.get("member", record["national_dex_id"])
        )
        filename = f"{record['slug']}.md"
        previous = public_records[index - 1] if index else None
        following = public_records[index + 1] if index + 1 < len(public_records) else None
        if only_pages is None or record["slug"] in only_pages:
            _write_text(
                output_root / filename,
                _render_record(
                    record,
                    previous,
                    following,
                    type_name_source,
                    preevolutions.get(record["slug"], []),
                    public_records,
                    move_lookup,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                ),
            )
            page_count += 1
        dex = record["national_dex_id"]
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "pokemon",
                    record.get("member", dex),
                    f"#{dex:03} {record['name']}",
                    record["slug"],
                ),
                "pokemon/index.md",
            )
        )
        stats = record["base_stats"]
        abilities = [value["name"] for value in record["abilities"] if value["name"]]
        ability_refs = [
            ROUTES.catalog_reference(
                entity_reference(
                    "ability",
                    value.get("id", value["name"]),
                    value["name"],
                    value.get("slug"),
                ),
                "pokemon/",
            )
            for value in record["abilities"]
            if value["name"]
        ]
        types = list(dict.fromkeys(value["name"] for value in record["types"]))
        egg_groups = list(
            dict.fromkeys(value["name"] for value in record["egg_groups"])
        )
        catalog_records.append(
            add_change_status({
                "id": record.get("member", dex),
                "dex": dex,
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "types": types,
                "abilities": abilities,
                "ability_refs": ability_refs,
                "egg_groups": egg_groups,
                "stats": stats,
                "bst": sum(stats.values()),
                "search_text": " ".join(
                    (record["name"], *types, *abilities, *egg_groups)
                ).lower(),
            }, change)
        )
    write_catalog(output_root, "pokemon", catalog_records)
    _write_text(
        output_root / "index.md",
        catalog_index(
            "Pokémon",
            "Extracted Pokémon and form data. Search, filter, and sort the complete roster.",
            "pokemon",
            fallback_links,
        ),
    )
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    type_name_source: dict[str, Any] | None = None,
    preevolutions: list[dict[str, Any]] | None = None,
    all_records: list[dict[str, Any]] | None = None,
    move_lookup: dict[int, dict[str, Any]] | None = None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
) -> str:
    source_file = f"pokemon/{record['slug']}.md"
    stats = record["base_stats"]
    held_items = [item for item in record.get("held_items", []) if item["id"]]
    machines = record["machines"]
    tutor_moves = record.get("tutor_moves", [])
    level_up_moves = record.get("level_up_moves", [])
    egg_moves = record.get("egg_moves", [])
    evolutions = record.get("evolutions", [])
    reference = record.get("reference") or {}
    baseline_stats = _comparison_base_stats(change, stats)
    lines = [
        f"# {record['name']}",
        "",
        *pokemon_summary(record),
        *_reference_entry(reference),
        *_sprite_gallery(record),
        *comparison_section(change, baseline_name, source_file, references),
        "## Base stats",
        "",
        *stat_list(stats, baseline_stats),
        "",
        "## Training",
        "",
        *_fact_grid(
            (
                ("EV yield", _ev_yield(record.get("ev_yields", {}))),
                ("Catch rate", str(record["catch_rate"])),
                ("Base experience", str(record["base_experience"])),
                ("Base friendship", str(record["base_friendship"])),
                ("Growth rate", _label(record["growth_rate"]["name"])),
                *(
                    (("Safari flee rate", str(record["safari_flee_rate"])),)
                    if record.get("safari_flee_rate")
                    else ()
                ),
            )
        ),
        "",
        "## Breeding",
        "",
        *_fact_grid(
            (
                ("Gender", _gender_ratio(record.get("gender_ratio"))),
                ("Hatch cycles", str(record["hatch_cycles"])),
                (
                    "Egg groups",
                    " / ".join(
                        _label(name)
                        for name in dict.fromkeys(
                            value["name"] for value in record["egg_groups"]
                        )
                    ),
                ),
            )
        ),
        "",
        "## Wild held items",
        "",
    ]
    if held_items:
        lines.extend(
            [
                "| Slot | Item | Item ID |",
                "| ---- | ---- | ------: |",
                *[
                    (
                        f"| {item['rarity'].title()} | "
                        f"{_item_link(item, source_file)} | {item['id']} |"
                    )
                    for item in held_items
                ],
                "",
            ]
        )
    else:
        lines.extend(["None.", ""])
    preevolutions = preevolutions or []
    lines.extend(["## Evolutions", ""])
    if preevolutions or evolutions:
        lines.extend(
            _evolution_list(all_records or [record], record, source_file)
        )
    else:
        lines.extend(["This Pokémon does not evolve.", ""])
    lines.extend(["## Learnset", "", "### Level-up moves", ""])
    move_lookup = move_lookup or {}
    _append_level_up_moves(lines, level_up_moves, source_file, move_lookup)
    lines.extend(["### Machines", ""])
    _append_machines(lines, machines, source_file, move_lookup)
    lines.extend(["### Move tutors", ""])
    _append_tutor_moves(lines, tutor_moves, source_file, move_lookup)
    lines.extend(["### Egg moves", ""])
    _append_egg_moves(lines, egg_moves, source_file, move_lookup)
    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Data provenance</summary>",
            "",
            (
                "Source: exact ROM record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`."
            ),
            *(
                [
                    "Type name source: ROM message table "
                    f"`{type_name_source['archive']}` member "
                    f"`{type_name_source['member']}`."
                ]
                if type_name_source is not None
                else []
            ),
            *(
                [
                    (
                        "Egg move source: exact ROM table entry at overlay offset "
                        f"`0x{record['egg_move_provenance']['overlay_offset']:X}`."
                    )
                ]
                if record.get("egg_move_provenance") is not None
                else []
            ),
            *(
                [
                    (
                        "Level-up learnset source: exact ROM record from "
                        f"`{record['learnset_provenance']['archive']}` member "
                        f"`{record['learnset_provenance']['member']}`."
                    )
                ]
                if record.get("learnset_provenance") is not None
                else []
            ),
            *(
                [
                    (
                        "Evolution source: exact ROM record from "
                        f"`{record['evolution_provenance']['archive']}` member "
                        f"`{record['evolution_provenance']['member']}`."
                    )
                ]
                if record.get("evolution_provenance") is not None
                else []
            ),
            "",
            "</details>",
            "",
        ]
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


_SPRITE_MATRIX_ROWS = (
    ("Front", "front_default", "front_shiny"),
    ("Front, female", "front_female", "front_shiny_female"),
    ("Back", "back_default", "back_shiny"),
    ("Back, female", "back_female", "back_shiny_female"),
)


def _sprite_gallery(record: dict[str, Any]) -> list[str]:
    sprites = record.get("sprites", [])
    if not sprites:
        return []
    by_key = {sprite["key"]: sprite for sprite in sprites}
    rows = [
        (label, by_key.get(default_key), by_key.get(shiny_key))
        for label, default_key, shiny_key in _SPRITE_MATRIX_ROWS
        if by_key.get(default_key) or by_key.get(shiny_key)
    ]
    if not rows:
        return []
    lines = [
        "## Sprites",
        "",
        '<div class="rw-sprite-matrix">',
        '<div class="rw-sprite-matrix__row rw-sprite-matrix__row--header">',
        '<span><span class="rw-visually-hidden">Sprite variant</span></span>'
        "<span>Normal</span><span>Shiny</span>",
        "</div>",
    ]
    for label, default_sprite, shiny_sprite in rows:
        lines.extend(
            [
                '<div class="rw-sprite-matrix__row">',
                f'<span class="rw-sprite-matrix__label">{escape(label)}</span>',
                _sprite_cell(default_sprite, record["name"]),
                _sprite_cell(shiny_sprite, record["name"]),
                "</div>",
            ]
        )
    lines.extend(["</div>", ""])
    return lines


def _sprite_cell(sprite: dict[str, str] | None, name: str) -> str:
    if sprite is None:
        return '<span class="rw-sprite-matrix__cell rw-sprite-matrix__cell--empty">—</span>'
    return (
        '<span class="rw-sprite-matrix__cell">'
        f'<img src="{escape(sprite["url"], quote=True)}" '
        f'alt="{escape(name)} — {escape(sprite["label"])}" loading="lazy">'
        "</span>"
    )


def _comparison_base_stats(
    comparison: dict[str, Any] | None,
    current: dict[str, int],
) -> dict[str, int] | None:
    if comparison is None or comparison.get("status") == "added":
        return None
    for change in comparison.get("changes", []):
        if change.get("field") == "base_stats":
            return change["before"]
    return current


def _index_preevolutions(
    records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    public_slugs = {record["slug"] for record in records}
    index: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        source = {
            "id": record.get("member", record["national_dex_id"]),
            "slug": record["slug"],
            "name": record["name"],
        }
        for evolution in record.get("evolutions", []):
            target_slug = evolution["target"].get("slug")
            if target_slug not in public_slugs:
                continue
            index.setdefault(target_slug, []).append(
                {"source": source, "evolution": evolution}
            )
    return index


def _evolution_list(
    records: list[dict[str, Any]],
    current: dict[str, Any],
    source_file: str,
) -> list[str]:
    source_url = source_file.removesuffix(".md") + "/"
    by_slug = {record["slug"]: record for record in records}
    for record in records:
        for evolution in record.get("evolutions", []):
            target = evolution["target"]
            slug = target.get("slug")
            if slug and slug not in by_slug:
                by_slug[slug] = {
                    "slug": slug,
                    "name": target["name"],
                    "member": target.get("id"),
                    "national_dex_id": target.get("id"),
                    "sprite": None,
                    "evolutions": [],
                }
    parents: dict[str, set[str]] = {}
    for record in records:
        for evolution in record.get("evolutions", []):
            target_slug = evolution["target"].get("slug")
            if target_slug in by_slug:
                parents.setdefault(target_slug, set()).add(record["slug"])

    ancestors = set()
    pending = [current["slug"]]
    while pending:
        slug = pending.pop()
        for parent in parents.get(slug, set()):
            if parent not in ancestors:
                ancestors.add(parent)
                pending.append(parent)
    roots = sorted(
        (
            slug
            for slug in {*ancestors, current["slug"]}
            if not parents.get(slug)
        ),
        key=lambda slug: by_slug[slug].get("member", 0),
    )
    if not roots:
        roots = [current["slug"]]
    lines = ['<div class="rw-evolution-list" aria-label="Evolution chain">']
    for root in roots:
        lines.extend(
            _evolution_row(
                by_slug[root], by_slug, current["slug"], source_url, set(), 0
            )
        )
    lines.extend(["</div>", ""])
    return lines


def _evolution_row(
    record: dict[str, Any],
    by_slug: dict[str, dict[str, Any]],
    current_slug: str,
    source_url: str,
    path: set[str],
    depth: int,
    condition: dict[str, Any] | None = None,
) -> list[str]:
    slug = record["slug"]
    is_current = slug == current_slug
    reference = entity_reference(
        "pokemon",
        record.get("member", record.get("national_dex_id", slug)),
        record["name"],
        slug,
    )
    href = ROUTES.published_href(reference, source_url)
    sprite = record.get("sprite") or {}
    media = '<span class="rw-evolution-row__placeholder" aria-hidden="true">?</span>'
    if sprite.get("url"):
        media = (
            f'<img src="{escape(sprite["url"], quote=True)}" alt="" '
            'loading="lazy">'
        )
    dex = record.get("national_dex_id")
    dex_label = f"#{dex:03}" if isinstance(dex, int) else ""
    name_escaped = escape(record["name"])
    if href is not None:
        current_attribute = ' aria-current="page"' if is_current else ""
        name = (
            f'<a href="{escape(href, quote=True)}"{current_attribute}>'
            f"{name_escaped}</a>"
        )
    else:
        name = name_escaped
    condition_html = (
        f'<span class="rw-evolution-row__condition">'
        f"{evolution_condition(condition, source_url)}</span>"
        if condition is not None
        else ""
    )
    current_badge = (
        '<span class="rw-evolution-row__current">Current</span>' if is_current else ""
    )
    row_class = "rw-evolution-row"
    if is_current:
        row_class += " rw-evolution-row--current"
    style_attribute = ""
    if depth:
        row_class += " rw-evolution-row--child"
        style_attribute = f' style="--rw-evolution-depth: {depth}"'
    lines = [
        line
        for line in [
            f'<div class="{row_class}"{style_attribute}>',
            f'<span class="rw-evolution-row__icon">{media}</span>',
            '<span class="rw-evolution-row__text">',
            f'<span class="rw-evolution-row__name">{name}</span>',
            condition_html,
            "</span>",
            current_badge,
            f'<span class="rw-evolution-row__dex">{dex_label}</span>',
            "</div>",
        ]
        if line
    ]
    next_path = {*path, slug}
    for evolution in record.get("evolutions", []):
        target = by_slug.get(evolution["target"].get("slug"))
        if target is not None and target["slug"] not in next_path:
            lines.extend(
                _evolution_row(
                    target,
                    by_slug,
                    current_slug,
                    source_url,
                    next_path,
                    depth + 1,
                    evolution,
                )
            )
    return lines


def _append_level_up_moves(
    lines: list[str],
    moves: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if not moves:
        lines.extend(["No level-up moves.", ""])
        return
    lines.extend(
        [
            "| Level | Move | Type | Class | Power | Accuracy | PP |",
            "| ----: | ---- | ---- | ----- | ----: | -------: | -: |",
            *[
                (
                    f"| {entry['level']} | "
                    f"{_record_link('move', entry['move'], source_file)} | "
                    f"{_move_cells(entry['move'], move_lookup)} |"
                )
                for entry in moves
            ],
            "",
        ]
    )


def _append_machines(
    lines: list[str],
    machines: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if machines and all("move" in machine for machine in machines):
        lines.extend(
            [
                "| Machine | Move | Type | Class | Power | Accuracy | PP |",
                "| ------- | ---- | ---- | ----- | ----: | -------: | -: |",
                *[
                    (
                        f"| {machine['name']} | "
                        f"{_record_link('move', machine['move'], source_file)} | "
                        f"{_move_cells(machine['move'], move_lookup)} |"
                    )
                    for machine in machines
                ],
                "",
            ]
        )
        return
    lines.extend([", ".join(machine["name"] for machine in machines) or "None", ""])


def _append_tutor_moves(
    lines: list[str],
    moves: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if not moves:
        lines.extend(["None.", ""])
        return
    lines.extend(
        [
            "| Move | Type | Class | Power | Accuracy | PP | Location | Requirement |",
            "| ---- | ---- | ----- | ----: | -------: | -: | -------- | ----------- |",
            *[
                (
                    f"| {_record_link('move', tutor['move'], source_file)} | "
                    f"{_move_cells(tutor['move'], move_lookup)} | "
                    f"{tutor['location']['name']} | {tutor_requirement(tutor)} |"
                )
                for tutor in moves
            ],
            "",
        ]
    )


def _append_egg_moves(
    lines: list[str],
    moves: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if not moves:
        lines.extend(["None.", ""])
        return
    lines.extend(
        [
            "| Move | Type | Class | Power | Accuracy | PP |",
            "| ---- | ---- | ----- | ----: | -------: | -: |",
            *[
                f"| {_record_link('move', move, source_file)} | "
                f"{_move_cells(move, move_lookup)} |"
                for move in moves
            ],
            "",
        ]
    )


def _move_cells(
    reference: dict[str, Any], move_lookup: dict[int, dict[str, Any]]
) -> str:
    move = move_lookup.get(reference.get("id"))
    if move is None:
        return "— | — | — | — | —"
    move_type = type_badges([move["type"]])
    damage_class = class_badge(move["damage_class"])
    power = move["power"] if move["power"] else "—"
    accuracy = f"{move['accuracy']}%" if move["accuracy"] else "—"
    return f"{move_type} | {damage_class} | {power} | {accuracy} | {move['pp']}"


def _reference_entry(reference: dict[str, Any]) -> list[str]:
    text = reference.get("flavor_text")
    if not isinstance(text, str) or not text.strip():
        return []
    version = reference.get("flavor_text_version") or reference.get("version")
    version_label = f"{_label(version)} Pokédex" if version else "Pokédex"
    return [
        '<figure class="rw-pokedex-entry">',
        f"<blockquote>{escape(' '.join(text.split()))}</blockquote>",
        f"<figcaption>{escape(version_label)}</figcaption>",
        "</figure>",
        "",
    ]


def _fact_grid(
    facts: tuple[tuple[str, str], ...], *, class_name: str = "rw-data-grid"
) -> list[str]:
    lines = [f'<dl class="{class_name}">']
    for name, value in facts:
        lines.append(
            f"<div><dt>{escape(name)}</dt><dd>{escape(value)}</dd></div>"
        )
    lines.append("</dl>")
    return lines


def _ev_yield(yields: dict[str, int]) -> str:
    fields = (
        ("HP", "hp"),
        ("Attack", "attack"),
        ("Defense", "defense"),
        ("Sp. Atk", "special_attack"),
        ("Sp. Def", "special_defense"),
        ("Speed", "speed"),
    )
    values = [
        f"{yields.get(key, 0)} {label}"
        for label, key in fields
        if yields.get(key)
    ]
    return ", ".join(values) or "None"


def _gender_ratio(value: int | None) -> str:
    if value == 255:
        return "Genderless"
    if value == 254:
        return "Female only"
    if value == 0:
        return "Male only"
    if not isinstance(value, int) or not 0 <= value <= 255:
        return "Unknown"
    female = (value + 1) / 256 * 100
    male = 100 - female
    return f"{male:g}% male / {female:g}% female"


def _label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"pokemon/{record['slug']}/"
    previous_link = (
        _record_nav_link(previous, f"← {previous['name']}", source_url, "prev")
        if previous is not None
        else None
    )
    following_link = (
        _record_nav_link(following, f"{following['name']} →", source_url, "next")
        if following is not None
        else None
    )
    lines.extend(record_navigation(previous_link, following_link, "Pokémon navigation"))


def _record_nav_link(
    record: dict[str, Any], label: str, source_url: str, direction: str
) -> str:
    href = ROUTES.published_href(
        entity_reference(
            "pokemon",
            record.get("member", record.get("national_dex_id")),
            label,
            record["slug"],
        ),
        source_url,
    )
    sprite_data = record.get("sprite") or {}
    return record_nav_link(href, label, direction, sprite_data.get("url"))


def _item_link(item: dict[str, Any], source_file: str) -> str:
    return _record_link("item", item, source_file)


def _record_link(kind: str, value: dict[str, Any], source_file: str) -> str:
    reference = entity_reference(
        kind,
        value.get("id", value.get("slug", value["name"])),
        value["name"],
        value.get("slug"),
    )
    return ROUTES.markdown_link(reference, source_file)

