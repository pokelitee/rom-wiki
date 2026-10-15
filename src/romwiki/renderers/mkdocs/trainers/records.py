"""Record-level facts shared by every trainer page component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.pipeline.enrichment.features import POST_BATTLE_HEALING, VICTORY_ITEMS
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    EntityReference,
    entity_reference,
)

DEFAULT_TRAINER_FEATURES = frozenset({POST_BATTLE_HEALING, VICTORY_ITEMS})

# Labels for the optional multi-format battle-mode field in the shared contract.
_BATTLE_MODE_LABELS = {
    0: "Single battle",
    1: "Double battle",
    2: "Triple battle",
    3: "Rotation battle",
}
_BATTLE_MODE_VALUES = {
    0: "single",
    1: "double",
    2: "triple",
    3: "rotation",
}


def trainer_label(record: Mapping[str, Any]) -> str:
    return " ".join(value for value in (record["class_name"], record["name"]) if value)


def trainer_route_id(trainer_id: int) -> str:
    return f"trainer-{trainer_id:04}"


def trainer_source_url(record: Mapping[str, Any]) -> str:
    return f"trainers/{trainer_route_id(record['trainer_id'])}/"


def combined_locations(record: dict[str, Any]) -> list[dict[str, Any]]:
    return record["locations"] + record.get("script_references", [])


def location_names(record: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(location["name"] for location in combined_locations(record))
    )


def battle_format_value(record: dict[str, Any]) -> str:
    if "battle_mode" in record:
        mode = record["battle_mode"]
        return _BATTLE_MODE_VALUES.get(mode, f"mode-{mode}")
    return "double" if record["double_battle"] else "single"


def battle_format_label(record: dict[str, Any]) -> str:
    if "battle_mode" in record:
        return _BATTLE_MODE_LABELS.get(
            record["battle_mode"], f"Battle mode {record['battle_mode']}"
        )
    return "Double battle" if record["double_battle"] else "Single battle"


def trainer_level_range(record: dict[str, Any]) -> str:
    levels = [member["level"] for member in record["party"]]
    return (
        f"{min(levels)}"
        if min(levels) == max(levels)
        else f"{min(levels)}–{max(levels)}"
    )


def _party_preview(record: dict[str, Any], limit: int = 3) -> str:
    species = [member["pokemon"]["name"] for member in record["party"]]
    preview = ", ".join(species[:limit])
    remaining = len(species) - limit
    return f"{preview}, +{remaining} more" if remaining > 0 else preview


def trainer_disambiguator(record: dict[str, Any]) -> str:
    """A compact "which one is this" hint for trainers sharing a display name.

    The source has no universal field distinguishing rematches or story
    variants from unrelated NPCs with the same name. Every entry therefore
    gets its level range and party species, which usually disambiguates it
    without inferring an unsupported relationship.
    """
    return f"Lv. {trainer_level_range(record)}: {_party_preview(record)}"


def group_ai_battle_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    grouped_items: dict[int | str, dict[str, Any]] = {}
    for item in record.get("ai_battle_items", []):
        if not item.get("name"):
            continue
        identity = item.get("id", item.get("slug", item["name"]))
        grouped = grouped_items.setdefault(identity, {"item": item, "quantity": 0})
        grouped["quantity"] += 1
    return list(grouped_items.values())


def ai_item_reference(item: dict[str, Any]) -> EntityReference:
    return entity_reference(
        "item",
        item.get("id", item.get("slug", item["name"])),
        item["name"],
        item.get("slug"),
    )


def ai_item_link(grouped: dict[str, Any], source_url: str) -> str:
    link = ROUTES.html_link(ai_item_reference(grouped["item"]), source_url)
    quantity = f" ×{grouped['quantity']}" if grouped["quantity"] > 1 else ""
    return f"{link}{quantity}"
