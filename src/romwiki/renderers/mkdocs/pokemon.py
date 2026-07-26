from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.components import (
    class_badge,
    display_name,
    empty_state,
    evolution_condition,
    fact_grid,
    machine_link,
    name_table_source,
    pokedex_quote,
    pokemon_summary,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_source_link,
    reference_sprite_cell,
    rom_record_source,
    sprite_with_link,
    stat_list,
    tutor_requirement,
    type_badges,
    version_availability_note,
    yes_no,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_markdown_link,
    entity_reference,
)


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
        following = (
            public_records[index + 1] if index + 1 < len(public_records) else None
        )
        if only_pages is None or record["slug"] in only_pages:
            write_text(
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
        unique_abilities = list(
            {
                value["name"]: value for value in record["abilities"] if value["name"]
            }.values()
        )
        abilities = [value["name"] for value in unique_abilities]
        ability_refs = [
            {
                **ROUTES.catalog_reference(
                    entity_reference(
                        "ability",
                        value.get("id", value["name"]),
                        value["name"],
                        value.get("slug"),
                    ),
                    "pokemon/",
                ),
                **({"hidden": True} if value.get("is_hidden") else {}),
            }
            for value in unique_abilities
        ]
        types = list(dict.fromkeys(value["name"] for value in record["types"]))
        egg_groups = list(
            dict.fromkeys(value["name"] for value in record["egg_groups"])
        )
        catalog_records.append(
            add_change_status(
                {
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
                },
                change,
            )
        )
    write_catalog(output_root, "pokemon", catalog_records)
    write_text(
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
        *version_availability_note(record),
        *pokemon_summary(record),
        *_reference_entry(reference),
        *_sprite_gallery(record),
        "## Base stats",
        "",
        *stat_list(stats, baseline_stats),
        "",
        *_battle_forms_section(record),
        "## Training",
        "",
        *fact_grid(
            (
                ("EV yield", _ev_yield(record.get("ev_yields", {}))),
                ("Catch rate", str(record["catch_rate"])),
                ("Base experience", str(record["base_experience"])),
                ("Base friendship", str(record["base_friendship"])),
                ("Growth rate", display_name(record["growth_rate"]["name"])),
                ("Safari flee rate", str(record["safari_flee_rate"])),
            )
        ),
        "",
        "## Breeding",
        "",
        *fact_grid(
            (
                ("Gender", _gender_ratio(record.get("gender_ratio"))),
                ("Hatch cycles", str(record["hatch_cycles"])),
                (
                    "Egg groups",
                    " / ".join(
                        display_name(name)
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
                "| Rarity | Item | Item ID |",
                "| ------ | ---- | ------: |",
                *[
                    (
                        f"| {item['rarity'].replace('_', ' ').title()} | "
                        f"{sprite_with_link(_item_sprite_cell(item, references), _item_link(item, source_file))} "
                        f"| {item['id']} |"
                    )
                    for item in held_items
                ],
                "",
            ]
        )
    else:
        lines.extend(empty_state("No wild held items."))
    lines.extend(["", "## Static encounters", ""])
    _append_static_encounters(lines, record.get("static_encounters", []))
    lines.extend(_other_forms_section(record, all_records or [record], source_file))
    preevolutions = preevolutions or []
    lines.extend(["## Evolutions", ""])
    if preevolutions or evolutions:
        lines.extend(_evolution_list(all_records or [record], record, source_file))
    else:
        lines.extend(empty_state("This Pokémon does not evolve."))
    lines.extend(["## Learnset", "", "### Level-up moves", ""])
    move_lookup = move_lookup or {}
    _append_level_up_moves(lines, level_up_moves, source_file, move_lookup)
    lines.extend(["### Machines", ""])
    _append_machines(lines, machines, source_file, move_lookup, references)
    lines.extend(["### Move tutors", ""])
    _append_tutor_moves(lines, tutor_moves, source_file, move_lookup)
    lines.extend(["### Egg moves", ""])
    _append_egg_moves(lines, egg_moves, source_file, move_lookup)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Personal-data member", f"`{record['member']}`"),
                        ("Flip battle sprite", yes_no(record["flip_sprite"])),
                    )
                ),
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                *(
                    [
                        name_table_source(
                            "Type",
                            type_name_source["archive"],
                            type_name_source["member"],
                        )
                    ]
                    if type_name_source is not None
                    else []
                ),
                *_egg_move_source(record),
                *(
                    [
                        rom_record_source(
                            record["learnset_provenance"]["archive"],
                            record["learnset_provenance"]["member"],
                            label="Level-up learnset source",
                        )
                    ]
                    if record.get("learnset_provenance") is not None
                    else []
                ),
                *(
                    [
                        rom_record_source(
                            record["evolution_provenance"]["archive"],
                            record["evolution_provenance"]["member"],
                            label="Evolution source",
                        )
                    ]
                    if record.get("evolution_provenance") is not None
                    else []
                ),
                *reference_source_link(record),
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _item_sprite_cell(item: dict[str, Any], references: ReferenceIndex | None) -> str:
    return reference_sprite_cell("item", item["id"], references)


_SPRITE_MATRIX_ROWS = (
    (
        "Front",
        "front_default",
        "front_shiny",
        "front_default_animated",
        "front_shiny_animated",
    ),
    (
        "Front, female",
        "front_female",
        "front_shiny_female",
        "front_female_animated",
        "front_shiny_female_animated",
    ),
    (
        "Back",
        "back_default",
        "back_shiny",
        "back_default_animated",
        "back_shiny_animated",
    ),
    (
        "Back, female",
        "back_female",
        "back_shiny_female",
        "back_female_animated",
        "back_shiny_female_animated",
    ),
)


def _sprite_gallery(record: dict[str, Any]) -> list[str]:
    sprites = record.get("sprites", [])
    by_key = {sprite["key"]: sprite for sprite in sprites}
    rows = [
        (
            label,
            by_key.get(default_key),
            by_key.get(shiny_key),
            by_key.get(animated_key),
            by_key.get(animated_shiny_key),
        )
        for label, default_key, shiny_key, animated_key, animated_shiny_key in _SPRITE_MATRIX_ROWS
        if by_key.get(default_key)
        or by_key.get(shiny_key)
        or by_key.get(animated_key)
        or by_key.get(animated_shiny_key)
    ]
    if not rows:
        return ["## Sprites", "", *empty_state("No sprites are available.")]
    has_animated = any(
        animated or animated_shiny for _, _, _, animated, animated_shiny in rows
    )
    lines = [
        "## Sprites",
        "",
        '<div class="rw-sprite-matrix'
        + (" rw-sprite-matrix--animated" if has_animated else "")
        + '">',
        '<div class="rw-sprite-matrix__row rw-sprite-matrix__row--header">',
        '<span><span class="rw-visually-hidden">Sprite variant</span></span>'
        "<span>Normal</span><span>Shiny</span>"
        + ("<span>Animated</span><span>Animated, shiny</span>" if has_animated else ""),
        "</div>",
    ]
    for (
        label,
        default_sprite,
        shiny_sprite,
        animated_sprite,
        animated_shiny_sprite,
    ) in rows:
        cells = [
            _sprite_cell(default_sprite, record["name"]),
            _sprite_cell(shiny_sprite, record["name"]),
        ]
        if has_animated:
            cells.extend(
                [
                    _sprite_cell(animated_sprite, record["name"]),
                    _sprite_cell(animated_shiny_sprite, record["name"]),
                ]
            )
        lines.extend(
            [
                '<div class="rw-sprite-matrix__row">',
                f'<span class="rw-sprite-matrix__label">{escape(label)}</span>',
                *cells,
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


def _sibling_forms(
    record: dict[str, Any], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    base_species = record.get("base_species")
    if not base_species:
        return []
    return [
        sibling
        for sibling in records
        if sibling["slug"] != record["slug"]
        and sibling.get("base_species") == base_species
    ]


def _battle_forms_section(record: dict[str, Any]) -> list[str]:
    """Real stats/typing for a species' battle-only transformations (e.g.
    Castform's weather forms, Darmanitan's Zen Mode) -- these have no PokéDB
    reference page or public record of their own (a player never
    independently owns one), so they're shown here rather than as a
    separate page, unlike a real alternate forme like Deoxys or Rotom.
    """
    forms = record.get("battle_forms")
    if not forms:
        return []
    lines = ["## Battle-only forms", ""]
    for form in forms:
        lines.extend(
            [
                f"### {escape(form['label'])}",
                "",
                type_badges(form["types"]),
                "",
                *stat_list(form["base_stats"]),
                "",
            ]
        )
    return lines


def _other_forms_section(
    record: dict[str, Any], records: list[dict[str, Any]], source_file: str
) -> list[str]:
    siblings = _sibling_forms(record, records)
    if not siblings:
        return []
    source_url = source_file.removesuffix(".md") + "/"
    forms = [record, *siblings]
    by_slug = {form["slug"]: form for form in forms}
    base = next(
        (form for form in forms if form.get("form") is None),
        forms[0],
    )
    lines = ['<div class="rw-record-tree" aria-label="Other forms">']
    lines.extend(_evolution_row(base, by_slug, record["slug"], source_url, set(), 0))
    for form in forms:
        if form["slug"] == base["slug"]:
            continue
        lines.extend(
            _evolution_row(form, by_slug, record["slug"], source_url, {base["slug"]}, 1)
        )
    lines.extend(["</div>", ""])
    return ["## Other forms", "", *lines]


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
        (slug for slug in {*ancestors, current["slug"]} if not parents.get(slug)),
        key=lambda slug: by_slug[slug].get("member", 0),
    )
    if not roots:
        roots = [current["slug"]]
    lines = ['<div class="rw-record-tree" aria-label="Evolution chain">']
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
    media = '<span class="rw-record-tree__placeholder" aria-hidden="true">?</span>'
    if sprite.get("url"):
        media = f'<img src="{escape(sprite["url"], quote=True)}" alt="" loading="lazy">'
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
        f'<span class="rw-record-tree__condition">'
        f"{evolution_condition(condition, source_url)}</span>"
        if condition is not None
        else ""
    )
    current_badge = (
        '<span class="rw-record-tree__current">Current</span>' if is_current else ""
    )
    row_class = "rw-record-tree__row"
    if is_current:
        row_class += " rw-record-tree__row--current"
    style_attribute = ""
    if depth:
        row_class += " rw-record-tree__row--child"
        style_attribute = f' style="--rw-record-tree-depth: {depth}"'
    lines = [
        line
        for line in [
            f'<div class="{row_class}"{style_attribute}>',
            f'<span class="rw-record-tree__icon">{media}</span>',
            '<span class="rw-record-tree__text">',
            f'<span class="rw-record-tree__name">{name}</span>',
            condition_html,
            "</span>",
            current_badge,
            f'<span class="rw-record-tree__dex">{dex_label}</span>',
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
        lines.extend(empty_state("No level-up moves."))
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
    references: ReferenceIndex | None,
) -> None:
    if machines and all("move" in machine for machine in machines):
        lines.extend(
            [
                "| Machine | Move | Type | Class | Power | Accuracy | PP |",
                "| ------- | ---- | ---- | ----- | ----: | -------: | -: |",
                *[
                    (
                        f"| {machine_link(machine, source_file, references)} | "
                        f"{_record_link('move', machine['move'], source_file)} | "
                        f"{_move_cells(machine['move'], move_lookup)} |"
                    )
                    for machine in machines
                ],
                "",
            ]
        )
        return
    if not machines:
        lines.extend(empty_state("No compatible machines."))
        return
    lines.extend(
        [
            ", ".join(
                machine_link(machine, source_file, references) for machine in machines
            ),
            "",
        ]
    )


def _append_tutor_moves(
    lines: list[str],
    moves: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if not moves:
        lines.extend(empty_state("No compatible tutor moves."))
        return
    lines.extend(
        [
            "| Move | Type | Class | Power | Accuracy | PP | Location | Requirement |",
            "| ---- | ---- | ----- | ----: | -------: | -: | -------- | ----------- |",
            *[
                (
                    f"| {_record_link('move', tutor['move'], source_file)} | "
                    f"{_move_cells(tutor['move'], move_lookup)} | "
                    f"{_tutor_location_link(tutor['location'], source_file)} | "
                    f"{tutor_requirement(tutor)} |"
                )
                for tutor in moves
            ],
            "",
        ]
    )


def _egg_move_source(record: dict[str, Any]) -> list[str]:
    provenance = record.get("egg_move_provenance")
    if provenance is None:
        return []
    if "archive" in provenance:
        return [
            rom_record_source(
                provenance["archive"], provenance["member"], label="Egg move source"
            )
        ]
    return [
        "Egg move source: exact ROM table entry at overlay offset "
        f"`0x{provenance['overlay_offset']:X}`."
    ]


def _append_egg_moves(
    lines: list[str],
    moves: list[dict[str, Any]],
    source_file: str,
    move_lookup: dict[int, dict[str, Any]],
) -> None:
    if not moves:
        lines.extend(empty_state("No egg moves."))
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


def _append_static_encounters(
    lines: list[str], encounters: list[dict[str, Any]]
) -> None:
    if not encounters:
        lines.extend(empty_state("No static (gift/single) encounters."))
        return
    lines.extend(
        [
            "| Level |",
            "| ----: |",
            *[
                f"| {'Egg' if entry['is_egg'] else entry['level']} |"
                for entry in encounters
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
    version_label = f"{display_name(version)} Pokédex" if version else "Pokédex"
    return pokedex_quote(text, version_label)


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
        f"{yields.get(key, 0)} {label}" for label, key in fields if yields.get(key)
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


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "pokemon",
            f"pokemon/{record['slug']}/",
            previous,
            following,
            aria_label="Pokémon navigation",
            identity=lambda value: value.get("member", value.get("national_dex_id")),
            route_key=lambda value: value["slug"],
            label=lambda value: value["name"],
            sprite_url=lambda value: (value.get("sprite") or {}).get("url"),
        )
    )


def _item_link(item: dict[str, Any], source_file: str) -> str:
    return _record_link("item", item, source_file)


def _tutor_location_link(location: dict[str, Any], source_file: str) -> str:
    if location.get("id") is None:
        return escape(location["name"])
    return entity_markdown_link(
        "location",
        location["id"],
        location["name"],
        source_file,
        route_key=location["id"],
    )


def _record_link(kind: str, value: dict[str, Any], source_file: str) -> str:
    return entity_markdown_link(
        kind,
        value.get("id", value.get("slug", value["name"])),
        value["name"],
        source_file,
        route_key=value.get("slug"),
    )
