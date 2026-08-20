from __future__ import annotations

from typing import Any

from romwiki.pipeline.semantics.encounter_identity import EncounterSourceType

FeatureRow = tuple[str, str, str, bool, int | str]
"""(catalog_key, summary_label, anchor, present, summary_value)."""

_WILD_ENCOUNTERS_ANCHOR = "wild-encounters"


def _conditional_encounter_rows(
    conditional_encounters: tuple[dict[str, Any], ...],
) -> list[FeatureRow]:
    """Rows for the conditional wild-encounter kinds linked from a page's
    "Wild encounters" section, so a reader can tell at a glance that a
    Headbutt tree, Hidden Grotto, or Daily Swarm exists here instead of only
    the general "encounters" feature. Each kind now has its own page under
    the encounters section (like ordinary methods and Safari Zone already
    do), so these rows link to the page's own "Wild encounters" section
    rather than to a same-page anchor.
    """
    grottoes = [
        encounter
        for encounter in conditional_encounters
        if encounter.get("source_type") == EncounterSourceType.HIDDEN_GROTTO
    ]
    has_swarm = any(
        encounter.get("source_type") == EncounterSourceType.DAILY_SWARM
        for encounter in conditional_encounters
    )
    has_headbutt = any(
        encounter.get("source_type") == EncounterSourceType.HEADBUTT
        for encounter in conditional_encounters
    )
    return [
        (
            "hidden grotto",
            "Hidden Grotto",
            _WILD_ENCOUNTERS_ANCHOR,
            bool(grottoes),
            len(grottoes),
        ),
        (
            "daily swarm",
            "Daily Swarm",
            _WILD_ENCOUNTERS_ANCHOR,
            has_swarm,
            "Yes",
        ),
        (
            "headbutt encounters",
            "Headbutt encounters",
            _WILD_ENCOUNTERS_ANCHOR,
            has_headbutt,
            "Yes",
        ),
    ]


def event_map_feature_rows(record: dict[str, Any]) -> list[FeatureRow]:
    """Notable sections on an event-map location page.

    Shared by the page's own summary card and the locations catalog's
    "Contains" column so the two can't drift into different vocabularies for
    the same section. Unlike encounter-map locations, event-map locations
    (Gen4 DPPt) never carry map-owned conditional encounters (Headbutt/Hidden
    Grotto/Daily Swarm): DPPt's profile contract has no layout key for them,
    and its own Headbutt-like/swarm-like mechanics (honey trees, Trophy
    Garden/Great Marsh rotations) are separate fields handled below instead.
    """
    has_encounters = record["encounter_id"] is not None
    daily_pool = record.get("daily_encounter_pool")
    daily_pool_anchor = (
        "great-marsh-daily-rotation"
        if daily_pool and daily_pool["kind"] == "great_marsh"
        else "trophy-garden-daily-rotation"
    )
    rows: list[FeatureRow] = [
        ("encounters", "Wild encounters", "wild-encounters", has_encounters, "Yes"),
        (
            "honey tree",
            "Honey tree",
            "honey-tree",
            bool(record.get("honey_tree")),
            "Yes",
        ),
        (
            "daily rotation",
            "Daily rotation",
            daily_pool_anchor,
            bool(daily_pool),
            "Yes",
        ),
    ]
    for catalog_key, label, key, anchor in (
        ("items", "Item pickups", "items", "item-pickups"),
        ("shops", "Shops", "shops", "shops"),
        ("gifts", "Gift Pokémon", "pokemon_gifts", "gift-pokemon"),
        ("trades", "In-game trades", "npc_trades", "in-game-trades"),
        (
            "static encounters",
            "Static encounters",
            "static_encounters",
            "static-encounters",
        ),
        (
            "roaming",
            "Roaming activations",
            "roaming_activations",
            "roaming-activations",
        ),
        (
            "game corner",
            "Game Corner prizes",
            "game_corner_prizes",
            "game-corner-prizes",
        ),
        ("trainers", "Trainers", "trainers", "trainers"),
        ("warps", "Warps", "warps", "warps"),
        ("connections", "Outdoor connections", "connections", "outdoor-connections"),
    ):
        count = len(record.get(key, []))
        rows.append((catalog_key, label, anchor, count > 0, count))
    return rows


def encounter_map_feature_rows(
    record: dict[str, Any],
    *,
    has_ordinary_encounters: bool,
    conditional_encounters: tuple[dict[str, Any], ...] = (),
) -> list[FeatureRow]:
    """Notable sections on an encounter-map location page.

    Shared by the page's own summary card and the locations catalog's
    "Contains" column so the two can't drift into different vocabularies for
    the same section.
    """
    has_encounters = has_ordinary_encounters or bool(conditional_encounters)
    rows: list[FeatureRow] = [
        ("encounters", "Wild encounters", "wild-encounters", has_encounters, "Yes"),
        *_conditional_encounter_rows(conditional_encounters),
    ]
    for catalog_key, label, key, anchor in (
        ("trainers", "Trainers", "trainers", "trainers"),
        ("warps", "Warps", "warps", "warps"),
        (
            "static encounters",
            "Static encounters",
            "static_encounters",
            "static-encounters",
        ),
        ("gifts", "Gift Pokémon", "pokemon_gifts", "gift-pokemon"),
        ("connections", "Outdoor connections", "connections", "outdoor-connections"),
        ("items", "Item pickups", "items", "item-pickups"),
        (
            "script-awarded items",
            "Script-awarded items",
            "script_awarded_items",
            "script-awarded-items",
        ),
        ("shops", "Shops", "shops", "shops"),
        (
            "marts",
            "Marts (contents undecoded)",
            "mart_references",
            "marts-contents-undecoded",
        ),
        ("trades", "In-game trades", "npc_trades", "in-game-trades"),
    ):
        count = len(record.get(key, []) or [])
        rows.append((catalog_key, label, anchor, count > 0, count))
    return rows
