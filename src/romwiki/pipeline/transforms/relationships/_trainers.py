"""Trainer-appearance relationships: which Pokemon appear in which parties."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from romwiki.schema.trainers import is_unused_trainer_slot

from ._shared import _pokemon_slug, _record_versions


@dataclass(frozen=True, slots=True)
class TrainerAppearance:
    pokemon_slug: str
    trainer_id: int
    trainer_name: str
    class_name: str | None
    party_position: int
    level: int
    held_item_id: int | None
    held_item_name: str | None
    held_item_slug: str | None
    locations: tuple[tuple[int | None, str], ...]
    linked: bool
    versions: tuple[str, ...]


def _trainer_appearances(
    records: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[TrainerAppearance]]:
    result: dict[str, list[TrainerAppearance]] = defaultdict(list)
    for record in records:
        if is_unused_trainer_slot(record):
            continue
        versions = _record_versions(record)
        locations = _trainer_locations(record)
        for position, member in enumerate(record.get("party", []), start=1):
            pokemon = member.get("pokemon")
            slug = _pokemon_slug(
                pokemon if isinstance(pokemon, Mapping) else None,
                member.get("species_id"),
                aliases,
            )
            if slug is None:
                continue
            held_item = member.get("held_item")
            held_item = held_item if isinstance(held_item, dict) else {}
            result[slug].append(
                TrainerAppearance(
                    pokemon_slug=slug,
                    trainer_id=record["trainer_id"],
                    trainer_name=record["name"],
                    class_name=record["class_name"],
                    party_position=position,
                    level=member["level"],
                    held_item_id=held_item.get("id"),
                    held_item_name=held_item.get("name"),
                    held_item_slug=held_item.get("slug"),
                    locations=locations,
                    linked=bool(locations),
                    versions=versions,
                )
            )
    return result


def _trainer_locations(
    record: Mapping[str, Any],
) -> tuple[tuple[int | None, str], ...]:
    values = []
    seen = set()
    for key in ("locations", "script_references"):
        for location in record.get(key, []):
            identity = (location.get("header_id"), location.get("name"))
            if isinstance(identity[1], str) and identity not in seen:
                seen.add(identity)
                values.append(identity)
    return tuple(values)


def _trainer_sort_key(value: TrainerAppearance) -> tuple[Any, ...]:
    return value.trainer_id, value.party_position, value.versions
