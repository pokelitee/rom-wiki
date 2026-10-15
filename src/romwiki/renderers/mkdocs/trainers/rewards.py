"""Prize money, AI battle items, and post-battle outcomes."""

from __future__ import annotations

from typing import Any

from romwiki.pipeline.enrichment.features import POST_BATTLE_HEALING, VICTORY_ITEMS
from romwiki.renderers.mkdocs.components import (
    MarkdownColumn,
    markdown_section,
    sprite_with_link,
    table_sprite_cell,
)
from romwiki.renderers.mkdocs.html import html_paragraph, html_table
from romwiki.renderers.mkdocs.references import ROUTES, entity_reference
from romwiki.renderers.mkdocs.trainers.records import ai_item_link, ai_item_reference

_EMPTY_NONE = '<span class="rw-summary__empty">None</span>'

_AI_ITEM_COLUMNS = (MarkdownColumn("Item"), MarkdownColumn("Quantity", "right"))


def ai_items_fact(grouped_items: list[dict[str, Any]], source_url: str) -> str:
    items = ", ".join(ai_item_link(grouped, source_url) for grouped in grouped_items)
    return f"<div><dt>AI items</dt><dd>{items or _EMPTY_NONE}</dd></div>"


def base_prize_money_facts(record: dict[str, Any]) -> list[str]:
    base_prize_money = record.get("base_prize_money")
    if not base_prize_money:
        return []
    return [
        "<div><dt>Base prize money</dt><dd>"
        f"&#8381;{base_prize_money['amount']:,}</dd></div>"
    ]


def post_battle_facts(
    record: dict[str, Any], source_url: str, features: frozenset[str]
) -> list[str]:
    """Facts for Gen V post-victory healing and items given to the player."""
    facts = []
    if POST_BATTLE_HEALING in features:
        result = (
            "Heals the player's party"
            if record.get("healer")
            else '<span class="rw-summary__empty">No healing</span>'
        )
        facts.append(f"<div><dt>After victory</dt><dd>{result}</dd></div>")
    if VICTORY_ITEMS in features:
        victory_item = record.get("victory_item")
        result = (
            ROUTES.html_link(
                entity_reference(
                    "item",
                    victory_item["id"],
                    victory_item["name"],
                    victory_item.get("slug"),
                ),
                source_url,
            )
            if victory_item
            else _EMPTY_NONE
        )
        facts.append(f"<div><dt>Victory item</dt><dd>{result}</dd></div>")
    return facts


def ai_battle_items_section(
    grouped_items: list[dict[str, Any]], source_url: str
) -> list[str]:
    if not grouped_items:
        return []
    rows = [
        (
            sprite_with_link(
                table_sprite_cell(grouped["item"].get("sprite_url")),
                ROUTES.html_link(ai_item_reference(grouped["item"]), source_url),
            ),
            str(grouped["quantity"]),
        )
        for grouped in grouped_items
    ]
    return markdown_section(
        "AI battle items",
        [
            *html_paragraph(
                "Items the trainer AI may use during battle. These are not prize items."
            ),
            *html_table(_AI_ITEM_COLUMNS, rows),
        ],
    )
