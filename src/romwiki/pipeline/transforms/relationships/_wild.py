"""Wild-encounter relationships: which Pokemon appear where, how, and when."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from romwiki.pipeline.enrichment.special_encounters import special_encounter_groups
from romwiki.pipeline.semantics.encounter_identity import (
    EncounterSourceType,
    encounter_route_key,
)

from ._shared import _location_display_name, _pokemon_slug, _record_variants


@dataclass(frozen=True, slots=True)
class WildEncounterReference:
    pokemon_slug: str
    area_id: int
    area_name: str
    encounter_route_key: int | str
    method: str
    minimum_level: int | None
    maximum_level: int | None
    chance: int | float | None
    condition: str | None
    season: str | None
    locations: tuple[tuple[int | None, str], ...]
    versions: tuple[str, ...]


_ENCOUNTER_METHODS = (
    ("walking", "Walking"),
    ("surf", "Surf"),
    ("rock_smash", "Rock Smash"),
    ("old_rod", "Old Rod"),
    ("good_rod", "Good Rod"),
    ("super_rod", "Super Rod"),
    ("grass_cave", "Grass / cave"),
    ("doubles_grass", "Doubles grass"),
    ("shaking_spots", "Shaking spots"),
    ("surfing", "Surfing"),
    ("surfing_spots", "Surfing spots"),
    ("fishing", "Fishing"),
    ("fishing_spots", "Fishing spots"),
)

_SAFARI_METHOD_LABELS = {
    "grass": "Grass",
    "surf": "Surf",
    "old-rod": "Old Rod",
    "good-rod": "Good Rod",
    "super-rod": "Super Rod",
}


def _wild_encounters(
    records: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[WildEncounterReference]]:
    result: dict[str, list[WildEncounterReference]] = defaultdict(list)
    location_index = _encounter_location_index(locations)
    for merged_record in records:
        for versions, record in _record_variants(merged_record):
            encounter_locations = _encounter_locations(record, location_index)
            common = {
                "area_id": record["area_id"],
                "area_name": (
                    " / ".join(dict.fromkeys(name for _, name in encounter_locations))
                    or record["name"]
                ),
                "encounter_route_key": encounter_route_key(record),
                "season": record.get("season"),
                "locations": encounter_locations,
                "versions": versions,
            }
            if record.get("source_type") == EncounterSourceType.HIDDEN_GROTTO:
                for slot in record.get("pokemon", []):
                    _add_wild_reference(
                        result,
                        aliases,
                        slot,
                        "Hidden Grotto",
                        f"{slot['pool_chance']}% pool; group {chr(ord('A') + slot['group'])}",
                        common,
                    )
                continue
            if record.get("source_type") == EncounterSourceType.DAILY_SWARM:
                _add_wild_reference(
                    result, aliases, record, "Daily Swarm", None, common
                )
                continue
            if record.get("source_type") == EncounterSourceType.HEADBUTT:
                for kind, slots in record.get("pools", {}).items():
                    for slot in slots:
                        _add_wild_reference(
                            result,
                            aliases,
                            slot,
                            f"Headbutt ({kind.title()} trees)",
                            None,
                            common,
                        )
                continue
            if record.get("source_type") == EncounterSourceType.SAFARI_ZONE:
                _add_safari_references(result, aliases, record, common)
                continue
            for key, label in _ENCOUNTER_METHODS:
                if key == "walking" and record.get("walking_variants"):
                    continue
                method = record.get(key)
                if not isinstance(method, dict) or not method.get("rate"):
                    continue
                for slot in method.get("slots", []):
                    _add_wild_reference(result, aliases, slot, label, None, common)
            _add_conditional_special_encounters(result, aliases, record, common)
    return result


def _add_safari_references(
    result: dict[str, list[WildEncounterReference]],
    aliases: Mapping[int | str, str],
    record: Mapping[str, Any],
    common: dict[str, Any],
) -> None:
    for method_name, method in record.get("methods", {}).items():
        label = _SAFARI_METHOD_LABELS.get(method_name, method_name)
        for time_name, slots in method.get("base_pools", {}).items():
            for slot in slots:
                _add_wild_reference(
                    result, aliases, slot, label, f"{time_name}; base pool", common
                )
        for encounter in method.get("block_encounters", []):
            requirements = ", ".join(
                f"{value['count']} {value['block_type']}"
                for value in encounter.get("requirements", [])
            )
            for time_name, slot in encounter.get("times", {}).items():
                condition = (
                    f"{time_name}; {requirements}" if requirements else time_name
                )
                _add_wild_reference(result, aliases, slot, label, condition, common)


def _add_conditional_special_encounters(
    result: dict[str, list[WildEncounterReference]],
    aliases: Mapping[int | str, str],
    record: Mapping[str, Any],
    common: dict[str, Any],
) -> None:
    special = record.get("special")
    if not isinstance(special, dict):
        return
    for period, method in record.get("walking_variants", {}).items():
        for slot in method.get("slots", []):
            _add_wild_reference(result, aliases, slot, "Walking", period, common)
    for group in special_encounter_groups(special):
        for slot in group.slots:
            _add_wild_reference(
                result,
                aliases,
                slot,
                group.method,
                group.condition,
                common,
            )


def _add_wild_reference(
    result: dict[str, list[WildEncounterReference]],
    aliases: Mapping[int | str, str],
    slot: Mapping[str, Any],
    method: str,
    condition: str | None,
    common: Mapping[str, Any],
) -> None:
    pokemon = slot.get("pokemon")
    slug = _pokemon_slug(
        pokemon if isinstance(pokemon, Mapping) else None,
        slot.get("species_id"),
        aliases,
    )
    if slug is None:
        return
    level = slot.get("level")
    minimum = slot.get("minimum_level", level)
    maximum = slot.get("maximum_level", level)
    result[slug].append(
        WildEncounterReference(
            pokemon_slug=slug,
            method=method,
            minimum_level=minimum if isinstance(minimum, int) else None,
            maximum_level=maximum if isinstance(maximum, int) else None,
            chance=slot.get("chance"),
            condition=condition,
            **common,
        )
    )


def _encounter_locations(
    record: Mapping[str, Any],
    location_index: Mapping[tuple[str, int], tuple[tuple[int, str], ...]],
) -> tuple[tuple[int | None, str], ...]:
    values: list[tuple[int | None, str]] = []
    location = record.get("location")
    if isinstance(location, Mapping) and isinstance(location.get("name"), str):
        values.append((location.get("header_id"), location["name"]))
    locations = record.get("locations")
    if isinstance(locations, list):
        values.extend(
            (location.get("header_id"), location["name"])
            for location in locations
            if isinstance(location, dict) and isinstance(location.get("name"), str)
        )
    lookup_key = (
        ("map-index", record["map_index"])
        if isinstance(record.get("map_index"), int)
        else ("area-id", record["area_id"])
    )
    values.extend(location_index.get(lookup_key, ()))
    if not values:
        names = record.get("location_names")
        if isinstance(names, list):
            values.extend((None, name) for name in names if isinstance(name, str))
    resolved: dict[tuple[str, int | str], tuple[int | None, str]] = {}
    for header_id, name in values:
        key = ("header", header_id) if header_id is not None else ("name", name)
        resolved[key] = (header_id, name)
    return tuple(resolved.values())


def _encounter_location_index(
    records: list[dict[str, Any]],
) -> dict[tuple[str, int], tuple[tuple[int, str], ...]]:
    values: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)
    for record in records:
        display_name = _location_display_name(record)
        if isinstance(record.get("encounter_id"), int):
            values[("area-id", record["encounter_id"])].append(
                (record["header_id"], display_name)
            )
        if isinstance(record.get("encounter_map_index"), int):
            values[("map-index", record["encounter_map_index"])].append(
                (record["header_id"], display_name)
            )
    return {key: tuple(dict.fromkeys(locations)) for key, locations in values.items()}


def _freeze_wild(
    values: Mapping[str, list[WildEncounterReference]],
) -> dict[str, tuple[WildEncounterReference, ...]]:
    result = {}
    for slug, entries in sorted(values.items()):
        grouped: dict[tuple[Any, ...], WildEncounterReference] = {}
        for entry in entries:
            key = (
                entry.pokemon_slug,
                entry.area_id,
                entry.area_name,
                entry.encounter_route_key,
                entry.method,
                entry.minimum_level,
                entry.maximum_level,
                entry.condition,
                entry.season,
                entry.locations,
                entry.versions,
            )
            existing = grouped.get(key)
            if existing is None or existing.chance is None or entry.chance is None:
                grouped.setdefault(key, entry)
                continue
            grouped[key] = WildEncounterReference(
                pokemon_slug=entry.pokemon_slug,
                area_id=entry.area_id,
                area_name=entry.area_name,
                encounter_route_key=entry.encounter_route_key,
                method=entry.method,
                minimum_level=entry.minimum_level,
                maximum_level=entry.maximum_level,
                chance=existing.chance + entry.chance,
                condition=entry.condition,
                season=entry.season,
                locations=entry.locations,
                versions=entry.versions,
            )
        result[slug] = tuple(sorted(grouped.values(), key=_wild_sort_key))
    return result


def _wild_sort_key(value: WildEncounterReference) -> tuple[Any, ...]:
    return (
        value.area_name,
        value.area_id,
        value.season or "",
        value.method,
        value.condition or "",
        value.minimum_level if value.minimum_level is not None else -1,
        value.maximum_level if value.maximum_level is not None else -1,
        value.chance if value.chance is not None else -1,
        value.versions,
    )
