"""Trainer page generation: page assembly, ordering, and catalog output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from romwiki.pipeline.transforms.relationships import RelationshipIndex
from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.comparisons import comparison_section, record_comparison
from romwiki.renderers.mkdocs.components import (
    escape_heading,
    record_navigation_for,
    with_resolved_location_labels,
)
from romwiki.renderers.mkdocs.html import count_markdown_tab_sets
from romwiki.renderers.mkdocs.references import ReferenceIndex
from romwiki.renderers.mkdocs.trainers.index import catalog_record, fallback_link
from romwiki.renderers.mkdocs.trainers.records import (
    DEFAULT_TRAINER_FEATURES,
    group_ai_battle_items,
    location_names,
    trainer_label,
    trainer_route_id,
    trainer_source_url,
)
from romwiki.renderers.mkdocs.trainers.rewards import ai_battle_items_section
from romwiki.renderers.mkdocs.trainers.sections import (
    locations_section,
    provenance,
    same_name_trainers_section,
    script_references_section,
)
from romwiki.renderers.mkdocs.trainers.summary import trainer_summary
from romwiki.renderers.mkdocs.trainers.variants import (
    BattleFamilyMembership,
    party_section,
)
from romwiki.schema.rendering import TrainerDataset
from romwiki.schema.trainers import is_unused_trainer_slot


def render_trainer_pages(
    dataset: TrainerDataset,
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    dataset_dict = cast(dict[str, Any], dataset)
    location_labels = relationships.location_labels if relationships else None
    source_records = cast(list[dict[str, Any]], dataset["records"])
    records = [
        with_resolved_location_labels(record, location_labels)
        for record in source_records
        if record["party"] and not is_unused_trainer_slot(record)
    ]
    records_by_id = {record["trainer_id"]: record for record in records}
    family_memberships: dict[int, list[BattleFamilyMembership]] = {}
    for family in dataset_dict.get("battle_families", []):
        for variant in family["variants"]:
            if variant["trainer_id"] in records_by_id:
                family_memberships.setdefault(variant["trainer_id"], []).append(
                    (family, variant)
                )
    dataset_features = frozenset(dataset_dict.get("features", DEFAULT_TRAINER_FEATURES))
    same_name_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (record["class_name"], record["name"])
        same_name_groups.setdefault(key, []).append(record)
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{trainer_route_id(record['trainer_id'])}.md"
                for record in records
                if only_pages is None
                or trainer_route_id(record["trainer_id"]) in only_pages
            ),
        },
    )
    linked = [
        record
        for record in records
        if record["locations"] or record.get("script_references", [])
    ]
    unlinked = [
        record
        for record in records
        if not record["locations"] and not record.get("script_references", [])
    ]
    sorted_linked = sorted(
        linked,
        key=lambda item: (
            (item["locations"] or item.get("script_references", []))[0]["name"],
            trainer_label(item),
            item["trainer_id"],
        ),
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    for is_linked, ordered in ((True, sorted_linked), (False, unlinked)):
        for index, record in enumerate(ordered):
            change = record_comparison(comparison, record["trainer_id"])
            route_id = trainer_route_id(record["trainer_id"])
            if only_pages is None or route_id in only_pages:
                write_text(
                    output_root / f"{route_id}.md",
                    _render_trainer(
                        record,
                        change,
                        comparison.get("baseline") if comparison else None,
                        references,
                        ordered[index - 1] if index else None,
                        ordered[index + 1] if index + 1 < len(ordered) else None,
                        same_name_groups[(record["class_name"], record["name"])],
                        dataset_features,
                        family_memberships.get(record["trainer_id"], []),
                        records_by_id,
                    ),
                )
                page_count += 1
            location_label = " / ".join(location_names(record)) if is_linked else ""
            fallback_links.append(fallback_link(record, location_label))
            catalog_records.append(
                catalog_record(
                    record, f"{route_id}/", location_label, is_linked, change
                )
            )
    write_catalog(output_root, "trainers", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Trainers",
            "Trainer parties and battle settings extracted directly from the ROM.",
            "trainers",
            fallback_links,
        ),
    )
    return page_count


def _render_trainer(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    same_name_records: list[dict[str, Any]] | None = None,
    features: frozenset[str] = DEFAULT_TRAINER_FEATURES,
    family_memberships: list[BattleFamilyMembership] | None = None,
    records_by_id: dict[int, dict[str, Any]] | None = None,
) -> str:
    """Assemble one trainer page.

    Headings stay Markdown so the page table of contents keeps working; every
    section body is raw HTML (see `renderers/mkdocs/html.py`). The comparison
    section is still Markdown, so its tab sets are numbered by
    `pymdownx.tabbed` and the raw Party tabs must take the next free index.
    """
    source_file = f"trainers/{trainer_route_id(record['trainer_id'])}.md"
    source_url = trainer_source_url(record)
    grouped_ai_items = group_ai_battle_items(record)
    comparison_lines = comparison_section(
        change, baseline_name, source_file, references
    )
    lines = [
        f"# {escape_heading(trainer_label(record))}",
        "",
        *trainer_summary(record, grouped_ai_items, source_url, features=features),
        *party_section(
            record,
            family_memberships or [],
            records_by_id or {},
            source_url,
            features=features,
            references=references,
            tab_set_index=count_markdown_tab_sets(comparison_lines) + 1,
        ),
        *ai_battle_items_section(grouped_ai_items, source_url),
        *locations_section(record["locations"], source_url),
        *script_references_section(record.get("script_references", []), source_url),
        *same_name_trainers_section(
            record, same_name_records or [], source_url, references
        ),
        *comparison_lines,
        *provenance(record),
        *record_navigation_for(
            "trainer",
            source_url,
            previous,
            following,
            aria_label="Trainer navigation",
            identity=lambda value: value["trainer_id"],
            route_key=lambda value: value["trainer_id"],
            label=trainer_label,
        ),
    ]
    return "\n".join(lines)
