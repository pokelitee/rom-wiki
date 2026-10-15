"""The Party section, including verified battle-family variant tabs."""

from __future__ import annotations

from typing import Any

from romwiki.renderers.mkdocs.components import (
    display_name,
    markdown_section,
    summary_section,
)
from romwiki.renderers.mkdocs.html import html_content_tabs, html_paragraph
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
)
from romwiki.renderers.mkdocs.trainers.party import party_cards
from romwiki.renderers.mkdocs.trainers.records import (
    DEFAULT_TRAINER_FEATURES,
    battle_format_label,
    group_ai_battle_items,
    trainer_level_range,
    trainer_route_id,
)
from romwiki.renderers.mkdocs.trainers.rewards import (
    ai_items_fact,
    base_prize_money_facts,
    post_battle_facts,
)

BattleFamilyMembership = tuple[dict[str, Any], dict[str, Any]]


def party_section(
    record: dict[str, Any],
    memberships: list[BattleFamilyMembership],
    records_by_id: dict[int, dict[str, Any]],
    source_url: str,
    *,
    features: frozenset[str] = DEFAULT_TRAINER_FEATURES,
    references: ReferenceIndex | None = None,
    tab_set_index: int = 1,
) -> list[str]:
    families = {family["id"]: family for family, _variant in memberships}
    if not families:
        return markdown_section(
            "Party", party_cards(record["party"], source_url, references)
        )
    prepared_tabs = _prepared_variant_tabs(
        record, families, records_by_id, source_url, features, references
    )
    if prepared_tabs and all(
        presentation == prepared_tabs[0][2] for _, _, presentation in prepared_tabs
    ):
        selection_links = [
            _trainer_link(
                candidate,
                f"{tab_label} ({trainer_route_id(candidate['trainer_id'])})",
                source_url,
            )
            for tab_label, candidate, _presentation in prepared_tabs
        ]
        return markdown_section(
            "Party",
            [
                *html_paragraph("Selections: " + " · ".join(selection_links)),
                *prepared_tabs[0][2],
            ],
        )
    tab_contents = [
        (
            tab_label,
            [
                *html_paragraph(
                    "Exact record: "
                    + _trainer_link(
                        candidate,
                        trainer_route_id(candidate["trainer_id"]),
                        source_url,
                    )
                ),
                *presentation,
            ],
        )
        for tab_label, candidate, presentation in prepared_tabs
    ]
    return markdown_section(
        "Party", html_content_tabs(tab_contents, set_index=tab_set_index)
    )


def _prepared_variant_tabs(
    record: dict[str, Any],
    families: dict[str, dict[str, Any]],
    records_by_id: dict[int, dict[str, Any]],
    source_url: str,
    features: frozenset[str],
    references: ReferenceIndex | None,
) -> list[tuple[str, dict[str, Any], list[str]]]:
    tabs: list[tuple[str, dict[str, Any], bool]] = []
    for family in sorted(families.values(), key=lambda value: value["order"]):
        variants = sorted(
            family["variants"],
            key=lambda value: (
                value["trainer_id"] != record["trainer_id"],
                value["order"],
            ),
        )
        for variant in variants:
            candidate = records_by_id.get(variant["trainer_id"])
            if candidate is None or not candidate.get("party"):
                continue
            is_difficulty = any(
                condition["kind"] == "difficulty-mode"
                for condition in variant["conditions"]
            )
            tabs.append(
                (variant_tab_label(variant, len(tabs) + 1), candidate, is_difficulty)
            )

    prepared_tabs: list[tuple[str, dict[str, Any], list[str]]] = []
    seen_labels: dict[str, int] = {}
    for label, candidate, is_difficulty in tabs:
        seen_labels[label] = seen_labels.get(label, 0) + 1
        tab_label = (
            label if seen_labels[label] == 1 else f"{label} ({seen_labels[label]})"
        )
        presentation = [
            *_variant_battle_details(
                candidate,
                source_url,
                is_difficulty=is_difficulty,
                features=features,
            ),
            *party_cards(candidate["party"], source_url, references),
        ]
        prepared_tabs.append((tab_label, candidate, presentation))
    return prepared_tabs


def _trainer_link(candidate: dict[str, Any], label: str, source_url: str) -> str:
    return ROUTES.html_link(
        entity_reference(
            "trainer", candidate["trainer_id"], label, candidate["trainer_id"]
        ),
        source_url,
    )


def _variant_battle_details(
    record: dict[str, Any],
    source_url: str,
    *,
    is_difficulty: bool,
    features: frozenset[str],
) -> list[str]:
    facts = []
    if "battle_mode" in record or "double_battle" in record:
        facts.append(
            f"<div><dt>Battle format</dt><dd>{battle_format_label(record)}</dd></div>"
        )
    facts.extend(
        [
            f"<div><dt>Party size</dt><dd>{len(record['party'])}</dd></div>",
            f"<div><dt>Level range</dt><dd>{trainer_level_range(record)}</dd></div>",
        ]
    )
    ai_flags = record.get("ai_flags")
    if isinstance(ai_flags, int):
        facts.append(
            f"<div><dt>AI flags</dt><dd><code>0x{ai_flags:08X}</code></dd></div>"
        )
    facts.append(ai_items_fact(group_ai_battle_items(record), source_url))
    facts.extend(base_prize_money_facts(record))
    facts.extend(post_battle_facts(record, source_url, features))
    if is_difficulty:
        facts.append(
            "<div><dt>Level basis</dt><dd>Stored ROM levels"
            '<abbr class="rw-inline-note" title="B2W2 may adjust the displayed '
            "level by difficulty after loading the party; stats still use the "
            'stored level.">*</abbr></dd></div>'
        )
    return summary_section("rw-trainer-variant-summary", facts)


def variant_tab_label(variant: dict[str, Any], generic_number: int) -> str:
    named_kinds = {
        "starter-choice",
        "difficulty-mode",
        "season",
        "rematch-stage",
        "sibling-version",
    }
    labels = [
        display_name(condition["value"])
        for condition in variant["conditions"]
        if condition["kind"] in named_kinds
    ]
    return " · ".join(labels) if labels else f"Variant {generic_number}"
