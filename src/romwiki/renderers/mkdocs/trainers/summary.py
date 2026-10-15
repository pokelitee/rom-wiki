"""The page-top trainer summary."""

from __future__ import annotations

from typing import Any

from romwiki.renderers.mkdocs.components import (
    display_name,
    summary_section,
    summary_section_link,
)
from romwiki.renderers.mkdocs.trainers.records import (
    DEFAULT_TRAINER_FEATURES,
    battle_format_label,
    location_names,
    trainer_level_range,
)
from romwiki.renderers.mkdocs.trainers.rewards import (
    ai_items_fact,
    base_prize_money_facts,
    post_battle_facts,
)


def _location_summary_value(record: dict[str, Any], names: list[str]) -> str:
    if not names:
        return '<span class="rw-summary__empty">—</span>'
    anchor = "locations" if record["locations"] else "scripted-battle-locations"
    return summary_section_link(" / ".join(names), anchor)


def trainer_summary(
    record: dict[str, Any],
    grouped_ai_items: list[dict[str, Any]],
    source_url: str,
    *,
    features: frozenset[str] = DEFAULT_TRAINER_FEATURES,
) -> list[str]:
    level_range = trainer_level_range(record)
    return summary_section(
        "rw-trainer-summary",
        [
            f"<div><dt>Trainer ID</dt><dd>trainer-{record['trainer_id']:04}</dd></div>",
            f"<div><dt>Class</dt><dd>{display_name(record['class_name'] or '')}</dd></div>",
            (
                "<div><dt>Location</dt><dd>"
                f"{_location_summary_value(record, location_names(record))}</dd></div>"
            ),
            (
                "<div><dt>Battle format</dt><dd>"
                f"{battle_format_label(record)}</dd></div>"
            ),
            "<div><dt>Party size</dt><dd>"
            f"{summary_section_link(len(record['party']), 'party')}</dd></div>",
            "<div><dt>Level range</dt><dd>"
            f"{summary_section_link(level_range, 'party')}</dd></div>",
            *base_prize_money_facts(record),
            ai_items_fact(grouped_ai_items, source_url),
            *post_battle_facts(record, source_url, features),
        ],
    )
