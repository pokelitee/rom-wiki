"""Trainer catalog records and no-JavaScript index fallback links."""

from __future__ import annotations

from typing import Any

from romwiki.renderers.mkdocs.comparisons import add_change_status
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    EntityReference,
    entity_reference,
    unique_references,
)
from romwiki.renderers.mkdocs.trainers.records import (
    battle_format_value,
    combined_locations,
    location_names,
    trainer_disambiguator,
    trainer_label,
)


def fallback_link(record: dict[str, Any], location_label: str) -> str:
    label = f"{trainer_label(record)} ({trainer_disambiguator(record)})"
    if location_label:
        label = f"{location_label} — {label}"
    return "- " + ROUTES.markdown_link(
        entity_reference("trainer", record["trainer_id"], label, record["trainer_id"]),
        "trainers/index.md",
    )


def _pokemon_reference(member: dict[str, Any]) -> EntityReference:
    pokemon = member["pokemon"]
    return entity_reference(
        "pokemon",
        pokemon.get("id", pokemon["slug"]),
        pokemon["name"],
        pokemon.get("page_slug", pokemon.get("slug")),
    )


def catalog_record(
    record: dict[str, Any],
    filename: str,
    location_label: str,
    linked: bool,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    levels = [member["level"] for member in record["party"]]
    names = location_names(record)
    party = [
        {
            "name": member["pokemon"]["name"],
            "level": member["level"],
            "pokemon_ref": ROUTES.catalog_reference(
                _pokemon_reference(member), "trainers/"
            ),
        }
        for member in record["party"]
    ]
    location_refs = unique_references(
        [
            entity_reference(
                "location",
                location["header_id"],
                location["name"],
                location.get("header_id"),
            )
            for location in combined_locations(record)
        ]
    )
    pokemon_refs = unique_references(
        _pokemon_reference(member) for member in record["party"]
    )
    species = [member["name"] for member in party]
    label = trainer_label(record)
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["trainer_id"],
            "route_id": route_id,
            "label": label,
            "url": filename,
            "class_name": record["class_name"],
            "name": record["name"],
            "locations": names,
            "location_label": location_label,
            "location_refs": [
                ROUTES.catalog_reference(reference, "trainers/")
                for reference in location_refs
            ],
            "linked": linked,
            "battle_format": battle_format_value(record),
            "double_battle": record["double_battle"],
            "party_size": len(record["party"]),
            "min_level": min(levels),
            "max_level": max(levels),
            "pokemon": species,
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "trainers/")
                for reference in pokemon_refs
            ],
            "party": party,
            "search_text": " ".join((label, route_id, *names, *species)).lower(),
        },
        change,
    )
