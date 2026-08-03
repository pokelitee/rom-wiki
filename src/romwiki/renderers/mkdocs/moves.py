from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from romwiki.pipeline.relationships import MoveLearnerReference, RelationshipIndex
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
    escape_table_cell,
    fact_grid,
    machine_html_link,
    name_table_source,
    pokemon_table,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_description,
    reference_source_link,
    reference_sprite_cell,
    reference_type_cell,
    rom_record_source,
    sprite_with_link,
    summary_section,
    tutor_requirement,
    type_badges,
    version_availability_note,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    escape_markdown,
    pokemon_record_link,
    resolved_reference,
)

_LEARNER_TABLE_SCHEMA_VERSION = 1
_LEARNER_TABLE_PAGE_SIZE = 50
_LEARNER_TABLE_PAGINATION_THRESHOLD = 50


def render_move_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
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
    name_source = dataset.get("name_sources", {}).get("move_names")
    dataset_features = frozenset(dataset.get("features", ("move-tutors", "egg-moves")))
    for index, record in enumerate(public_records):
        change = record_comparison(comparison, record["move_id"])
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
                    name_source,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    dataset_features,
                    relationships,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "move",
                    record["move_id"],
                    record["name"],
                    record["slug"],
                ),
                "moves/index.md",
            )
        )
        machines = [machine["name"] for machine in record.get("machines", [])]
        replaced_name = record["replaces"]["name"] if record.get("replaces") else None
        access_methods = [
            method
            for method, available in (
                (
                    "level up",
                    bool(
                        relationships
                        and relationships.move_level_up_learners.get(record["move_id"])
                    ),
                ),
                ("machine", bool(machines)),
                ("move tutor", bool(record.get("tutors"))),
                ("egg move", bool(record.get("egg_move_pokemon"))),
            )
            if available
        ]
        learner_counts, learner_count = _learner_summary(record, relationships)
        if relationships is not None and learner_count == 0:
            access_methods.append("no known learners")
        catalog_records.append(
            add_change_status(
                {
                    "id": record["move_id"],
                    "label": record["name"],
                    "slug": record["slug"],
                    "url": f"{record['slug']}/",
                    "type": record["type"]["name"],
                    "damage_class": record["damage_class"]["name"],
                    "power": record["power"],
                    "accuracy": record["accuracy"],
                    "pp": record["pp"],
                    "machines": machines,
                    "access_methods": access_methods,
                    "learner_count": learner_count,
                    "learner_counts": learner_counts,
                    "search_text": " ".join(
                        (
                            record["name"],
                            *machines,
                            *access_methods,
                            *((replaced_name,) if replaced_name else ()),
                        )
                    ).lower(),
                },
                change,
            )
        )
    write_catalog(output_root, "moves", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Moves",
            "Move mechanics extracted directly from the game image.",
            "moves",
            fallback_links,
        ),
    )
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    name_source: dict[str, Any] | None = None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    features: frozenset[str] = frozenset({"move-tutors", "egg-moves"}),
    relationships: RelationshipIndex | None = None,
) -> str:
    source_file = f"moves/{record['slug']}.md"
    source_url = source_file.removesuffix(".md") + "/"
    additional_properties = []
    if record.get("machines"):
        additional_properties.append(
            (
                "Machine",
                ", ".join(
                    machine_html_link(machine, source_url, references)
                    for machine in record["machines"]
                ),
            )
        )
    if record.get("tutors"):
        additional_properties.append(
            (
                "Move tutor",
                ", ".join(
                    _tutor_location_link_html(tutor["location"], source_url)
                    for tutor in record["tutors"]
                ),
            )
        )
    if record.get("replaces") and change is None:
        additional_properties.append(("Replaces", record["replaces"]["name"]))
    if record["priority"]:
        additional_properties.append(("Priority", f"{record['priority']:+d}"))
    if record["effect_chance"]:
        additional_properties.append(("Effect chance", f"{record['effect_chance']}%"))
    lines = [
        f"# {record['name']}",
        "",
        *version_availability_note(record),
        *_move_summary(record),
        *reference_description(
            record, "No PokéDB reference data is available for this move."
        ),
        *_reference_effects_section(record),
    ]
    if additional_properties:
        lines.extend(
            [
                "## Additional battle properties",
                "",
                *fact_grid(
                    tuple(
                        (
                            label,
                            value
                            if label in ("Machine", "Move tutor")
                            else escape(value),
                        )
                        for label, value in additional_properties
                    ),
                    escape_values=False,
                ),
                "",
            ]
        )
    lines.extend(
        _learned_by_section(
            record,
            source_file,
            references,
            relationships,
            features,
        )
    )
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Effect ID", f"`{record['effect_id']}`"),
                        ("Target ID", f"`0x{record['target_id']:04X}`"),
                        ("Flags", f"`0x{record['flags']:02X}`"),
                        # Absent for engines with no Contests (e.g. Gen V removed
                        # them), rather than merely unresolved.
                        *(
                            (("Contest effect ID", f"`{record['contest_effect_id']}`"),)
                            if "contest_effect_id" in record
                            else ()
                        ),
                        *(
                            (("Contest type ID", f"`{record['contest_type_id']}`"),)
                            if "contest_type_id" in record
                            else ()
                        ),
                    )
                ),
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "Effect, target, and flag IDs are shown in their native engine "
                "representation.",
                "The move record stores only an opaque effect ID rather than a "
                "description; the Effect section above (including its "
                "supplementary battle-mechanic facts and Pokédex quote) comes from "
                "PokéDB / PokéAPI reference data and describes the base game — a "
                "hack that changes this move's effect ID may behave differently.",
                *(
                    [
                        name_table_source(
                            "Move", name_source["archive"], name_source["member"]
                        )
                    ]
                    if name_source is not None
                    else []
                ),
                *reference_source_link(record),
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _move_summary(record: dict[str, Any]) -> list[str]:
    return summary_section(
        "rw-move-summary",
        [
            f"<div><dt>Move ID</dt><dd>{record['move_id']}</dd></div>",
            f"<div><dt>Type</dt><dd>{type_badges([record['type']])}</dd></div>",
            f"<div><dt>Class</dt><dd>{class_badge(record['damage_class'])}</dd></div>",
            f"<div><dt>Power</dt><dd>{_optional_value(record['power'])}</dd></div>",
            f"<div><dt>Accuracy</dt><dd>{_accuracy(record['accuracy'])}</dd></div>",
            f"<div><dt>PP</dt><dd>{record['pp']}</dd></div>",
        ],
    )


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "move",
            f"moves/{record['slug']}/",
            previous,
            following,
            aria_label="Move navigation",
            identity=lambda value: value["move_id"],
            route_key=lambda value: value["slug"],
            label=lambda value: value["name"],
        )
    )


def _reference_effects_section(record: dict[str, Any]) -> list[str]:
    """Fold PokéDB's supplementary battle-mechanic facts into the Effect section.

    These are just as PokéDB-sourced as the Effect prose above them, so they
    nest under its heading (mirroring how pokemon.py nests "### Level-up
    moves" etc. under "## Learnset") rather than getting a section of their
    own — keeping only two top-level data buckets on the page (PokéDB-sourced
    "Effect", ROM-sourced "Additional battle properties"), matching every
    other kind's page. Rendered through the same `fact_grid()` component as
    "Additional battle properties" so the two sibling lists of move facts
    carry the same visual weight.
    """
    properties = _reference_battle_properties(record)
    if not properties:
        return []
    reference = record.get("reference") or {}
    heading_level = (
        "###"
        if any(
            reference.get(field) for field in ("short_effect", "effect", "flavor_text")
        )
        else "##"
    )
    return [
        f"{heading_level} Additional effects",
        "",
        *fact_grid(tuple(properties)),
        "",
    ]


def _reference_battle_properties(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Supplementary battle mechanics PokéDB resolves but the ROM never stores.

    Move records only carry an opaque `effect_id` the engine's native code
    interprets; things like crit-rate boosts, drain/heal percentages, and
    secondary-effect chances aren't ROM data at all, so PokéDB is the only
    source for them.
    """
    reference = record.get("reference") or {}
    metadata = reference.get("metadata") or {}
    properties: list[tuple[str, str]] = []
    stat_changes = [
        f"{display_name(change['stat'])} {change['change']:+d}"
        for change in reference.get("stat_changes") or []
        if change.get("change")
    ]
    if stat_changes:
        label = ", ".join(stat_changes)
        stat_chance = metadata.get("stat_chance")
        if stat_chance:
            label += f" ({stat_chance}% chance)"
        properties.append(("Stat changes", label))
    if metadata.get("crit_rate"):
        properties.append(("Critical-hit rate", f"+{metadata['crit_rate']} stage"))
    drain = metadata.get("drain")
    if drain:
        label = "HP drain" if drain > 0 else "Recoil"
        properties.append((label, f"{abs(drain)}% of damage dealt"))
    if metadata.get("healing"):
        properties.append(("Healing", f"{metadata['healing']}% of max HP"))
    if metadata.get("flinch_chance"):
        properties.append(("Flinch chance", f"{metadata['flinch_chance']}%"))
    ailment = metadata.get("ailment")
    if ailment and ailment != "none":
        label = display_name(ailment)
        ailment_chance = metadata.get("ailment_chance")
        if ailment_chance:
            label += f" ({ailment_chance}% chance)"
        properties.append(("Secondary effect", label))
    if metadata.get("min_hits") is not None:
        properties.append(
            ("Hits", _hit_range(metadata["min_hits"], metadata["max_hits"]))
        )
    if metadata.get("min_turns") is not None:
        properties.append(
            ("Duration", _turn_range(metadata["min_turns"], metadata["max_turns"]))
        )
    return properties


def _hit_range(minimum: int, maximum: int) -> str:
    return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"


def _turn_range(minimum: int, maximum: int) -> str:
    if minimum == maximum:
        return f"{minimum} turn" if minimum == 1 else f"{minimum} turns"
    return f"{minimum}-{maximum} turns"


def _optional_value(value: int) -> str:
    return str(value) if value else "—"


def _accuracy(value: int) -> str:
    return "Always hits" if value in {0, 101} else f"{value}%"


def _learned_by_section(
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    relationships: RelationshipIndex | None,
    features: frozenset[str],
) -> list[str]:
    level_up = (
        relationships.move_level_up_learners.get(record["move_id"], ())
        if relationships
        else ()
    )
    machines = (
        relationships.move_machine_learners.get(record["move_id"], ())
        if relationships
        else ()
    )
    sections = [
        (
            "Level up",
            _relationship_learner_table(
                level_up, source_file, references, detail="level"
            ),
        ),
        (
            "Machines",
            _relationship_learner_table(
                machines, source_file, references, detail="machine"
            ),
        ),
    ]
    if "move-tutors" in features:
        sections.append(
            (
                "Move tutors",
                (
                    _tutor_compatibility(record, source_file, references)
                    if record.get("tutors")
                    else empty_state("No compatible move tutors.")
                ),
            )
        )
    if "egg-moves" in features:
        sections.append(
            (
                "Egg moves",
                _egg_move_learners(record, source_file, references),
            )
        )
    lines = ["## Learned by", ""]
    for heading, content in sections:
        lines.extend([f"### {heading}", "", *content])
    return lines


def _relationship_learner_table(
    learners: tuple[MoveLearnerReference, ...],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    detail: str,
) -> list[str]:
    if not learners:
        return empty_state(
            "No level-up learners."
            if detail == "level"
            else "No machine-compatible Pokémon."
        )
    detail_heading = "Level" if detail == "level" else "Machine"
    show_sprites = len(learners) <= _LEARNER_TABLE_PAGINATION_THRESHOLD
    fallback_rows = []
    payload_rows = []
    for learner in learners:
        pokemon = {
            "member": learner.pokemon_id,
            "name": learner.pokemon_name,
            "slug": learner.pokemon_slug,
        }
        detail_value = (
            str(learner.level)
            if detail == "level" and learner.level is not None
            else learner.machine_name or "—"
        )
        fallback_rows.append(
            "| "
            f"{_pokemon_table_link(pokemon, source_file, references, show_sprites)} | "
            f"{escape_table_cell(display_name(learner.pokemon_form)) if learner.pokemon_form else '—'} | "
            f"{escape_table_cell(detail_value)} | "
            f"{_learner_versions(learner.versions)} |"
        )
        payload_rows.append(
            [
                _learner_pokemon_cell(pokemon, source_file, references),
                _learner_text_cell(
                    display_name(learner.pokemon_form) if learner.pokemon_form else "—"
                ),
                _learner_text_cell(detail_value),
                _learner_text_cell(_learner_version_text(learner.versions)),
            ]
        )
    header = [
        f"| Pokémon | Form | {detail_heading} | Version |",
        "| ------- | ---- | ------- | ------- |",
    ]
    fallback = pokemon_table(header, fallback_rows)
    if show_sprites:
        return fallback
    return _paginated_learner_table(
        columns=["Pokémon", "Form", detail_heading, "Version"],
        rows=payload_rows,
        fallback=fallback,
        table_key=detail,
        label=f"{detail_heading} learners",
    )


def _learner_versions(versions: tuple[str, ...]) -> str:
    return escape_table_cell(_learner_version_text(versions))


def _learner_version_text(versions: tuple[str, ...]) -> str:
    return " / ".join(display_name(version) for version in versions) or "—"


def _learner_summary(
    record: dict[str, Any],
    relationships: RelationshipIndex | None,
) -> tuple[dict[str, int], int]:
    move_id = record["move_id"]
    learners_by_method = {
        "level_up": {
            learner.pokemon_slug
            for learner in (
                relationships.move_level_up_learners.get(move_id, ())
                if relationships
                else ()
            )
        },
        "machine": {
            learner.pokemon_slug
            for learner in (
                relationships.move_machine_learners.get(move_id, ())
                if relationships
                else ()
            )
        },
        "move_tutor": {
            pokemon["slug"]
            for tutor in record.get("tutors", ())
            for pokemon in tutor.get("compatible_pokemon", ())
        },
        "egg_move": {pokemon["slug"] for pokemon in record.get("egg_move_pokemon", ())},
    }
    counts = {
        method: len(pokemon_slugs)
        for method, pokemon_slugs in learners_by_method.items()
    }
    all_learners = set().union(*learners_by_method.values())
    return counts, len(all_learners)


def _tutor_compatibility(
    record: dict[str, Any], source_file: str, references: ReferenceIndex | None
) -> list[str]:
    lines = []
    for tutor_index, tutor in enumerate(record["tutors"], start=1):
        costs = tutor_requirement(tutor)
        location = _tutor_location_link(tutor["location"], source_file)
        lines.extend([f"**{location} — {costs}:**", ""])
        lines.extend(
            _pokemon_sprite_table(
                tutor["compatible_pokemon"],
                source_file,
                references,
                "No compatible Pokémon.",
                table_key=f"tutor_{tutor_index}",
                table_label=f"{tutor['location']['name']} compatible Pokémon",
            )
        )
    return lines


def _tutor_location_link(location: dict[str, Any], source_file: str) -> str:
    if location.get("id") is None:
        return escape_markdown(location["name"])
    return ROUTES.markdown_link(
        entity_reference("location", location["id"], location["name"], location["id"]),
        source_file,
    )


def _tutor_location_link_html(location: dict[str, Any], source_url: str) -> str:
    if location.get("id") is None:
        return escape(location["name"])
    return ROUTES.html_link(
        entity_reference("location", location["id"], location["name"], location["id"]),
        source_url,
    )


def _egg_move_learners(
    record: dict[str, Any], source_file: str, references: ReferenceIndex | None
) -> list[str]:
    return _pokemon_sprite_table(
        record["egg_move_pokemon"],
        source_file,
        references,
        "No egg move learners.",
        table_key="egg",
        table_label="Egg move learners",
    )


def _pokemon_sprite_table(
    pokemon: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
    empty_message: str,
    *,
    table_key: str = "learners",
    table_label: str = "Move learners",
) -> list[str]:
    if not pokemon:
        return empty_state(empty_message)
    show_sprites = len(pokemon) <= _LEARNER_TABLE_PAGINATION_THRESHOLD
    fallback = pokemon_table(
        ["| Pokémon | Type |", "| ------- | ---- |"],
        [
            (
                f"| {_pokemon_table_link(value, source_file, references, show_sprites)} | "
                f"{reference_type_cell('pokemon', value.get('member'), references)} |"
            )
            for value in pokemon
        ],
    )
    if show_sprites:
        return fallback
    return _paginated_learner_table(
        columns=["Pokémon", "Type"],
        rows=[
            [
                _learner_pokemon_cell(value, source_file, references),
                _learner_type_cell(value, references),
            ]
            for value in pokemon
        ],
        fallback=fallback,
        table_key=table_key,
        label=table_label,
    )


def _paginated_learner_table(
    *,
    columns: list[str],
    rows: list[list[dict[str, Any]]],
    fallback: list[str],
    table_key: str,
    label: str,
) -> list[str]:
    payload = json.dumps(
        {
            "schema_version": _LEARNER_TABLE_SCHEMA_VERSION,
            "label": label,
            "page_param": f"{table_key}_page",
            "page_size": _LEARNER_TABLE_PAGE_SIZE,
            "columns": columns,
            "rows": rows,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload = (
        payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    return [
        '<div class="rw-learner-table" data-rw-learner-table markdown="1">',
        '<div class="rw-learner-table__interactive" '
        "data-rw-learner-interactive hidden></div>",
        '<script type="application/json" data-rw-learner-data>',
        payload,
        "</script>",
        '<div class="rw-learner-table__fallback" '
        'data-rw-learner-fallback markdown="1">',
        "",
        *fallback,
        "</div>",
        "</div>",
        "",
    ]


def _learner_pokemon_cell(
    value: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> dict[str, Any]:
    identifier = value.get("member", value.get("id", value.get("slug", value["name"])))
    reference = resolved_reference(
        "pokemon",
        identifier,
        value["name"],
        value.get("slug"),
        index=references,
    )
    return {
        "kind": "pokemon",
        "label": value["name"],
        "url": ROUTES.published_href(reference, source_file.removesuffix(".md") + "/"),
        "sprite_url": reference.sprite_url,
    }


def _learner_type_cell(
    value: dict[str, Any], references: ReferenceIndex | None
) -> dict[str, Any]:
    identifier = value.get("member", value.get("id"))
    types = (
        references.types("pokemon", identifier)
        if references is not None and identifier is not None
        else None
    )
    return {
        "kind": "types",
        "values": [
            {"name": str(type_["name"]), "label": display_name(str(type_["name"]))}
            for type_ in types or ()
        ],
    }


def _learner_text_cell(value: str) -> dict[str, str]:
    return {"kind": "text", "value": value}


def _pokemon_table_link(
    value: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    show_sprite: bool,
) -> str:
    link = pokemon_record_link(value, source_file)
    if not show_sprite:
        return link
    return sprite_with_link(
        reference_sprite_cell("pokemon", value.get("member"), references),
        link,
    )
