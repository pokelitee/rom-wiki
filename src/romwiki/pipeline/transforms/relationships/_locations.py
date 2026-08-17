"""Location <-> wild-encounter cross-references, and map-owned conditional
encounters (headbutt/grotto/swarm) indexed by their owning location."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from romwiki.pipeline.semantics.encounter_identity import (
    CONDITIONAL_ENCOUNTER_SOURCES,
    MAP_OWNED_CONDITIONAL_SOURCES,
    encounter_route_key,
)
from romwiki.util.errors import DataSourceError

from ._shared import _location_display_name, _record_variants, _record_versions


@dataclass(frozen=True, slots=True)
class LocationEncounterReference:
    header_id: int
    area_id: int
    map_index: int
    season: str | None
    encounter_route_key: int | str
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EncounterLocationReference:
    encounter_route_key: int | str
    header_id: int
    location_name: str
    section_name: str | None
    versions: tuple[str, ...]


def _location_conditional_encounters(
    records: list[dict[str, Any]],
) -> dict[int, tuple[dict[str, Any], ...]]:
    values: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("source_type") not in MAP_OWNED_CONDITIONAL_SOURCES:
            continue
        location = record.get("location")
        if not isinstance(location, Mapping):
            continue
        header_id = location.get("header_id")
        if isinstance(header_id, int):
            values[header_id].append(record)
    return {
        header_id: tuple(sorted(entries, key=lambda entry: entry["area_id"]))
        for header_id, entries in sorted(values.items())
    }


def _location_encounters(
    locations: list[dict[str, Any]],
    encounters: list[dict[str, Any]],
    *,
    require_matches: bool,
) -> dict[int, list[LocationEncounterReference]]:
    by_map_index: dict[int, list[tuple[tuple[str, ...], dict[str, Any]]]] = defaultdict(
        list
    )
    for merged_record in encounters:
        for versions, record in _record_variants(merged_record):
            if record.get("source_type") in CONDITIONAL_ENCOUNTER_SOURCES:
                continue
            map_index = record.get("map_index", record.get("area_id"))
            if isinstance(map_index, int):
                by_map_index[map_index].append((versions, record))

    result: dict[int, list[LocationEncounterReference]] = defaultdict(list)
    unmatched = []
    for location in locations:
        map_index = location.get("encounter_map_index")
        if not isinstance(map_index, int):
            continue
        matching_encounters = by_map_index.get(map_index, [])
        if require_matches and not matching_encounters:
            unmatched.append((location["header_id"], map_index))
            continue
        location_versions = _record_versions(location)
        for encounter_versions, encounter in matching_encounters:
            result[location["header_id"]].append(
                LocationEncounterReference(
                    header_id=location["header_id"],
                    area_id=encounter["area_id"],
                    map_index=map_index,
                    season=encounter.get("season"),
                    encounter_route_key=encounter_route_key(encounter),
                    versions=encounter_versions or location_versions,
                )
            )
    if unmatched:
        examples = ", ".join(
            f"header {header_id} -> map {map_index}"
            for header_id, map_index in unmatched[:10]
        )
        suffix = f" (and {len(unmatched) - 10} more)" if len(unmatched) > 10 else ""
        raise DataSourceError(
            "Location wild-encounter references have no matching encounter "
            f"records: {examples}{suffix}"
        )
    return result


def _freeze_location_encounters(
    values: Mapping[int, list[LocationEncounterReference]],
) -> dict[int, tuple[LocationEncounterReference, ...]]:
    result = {}
    for header_id, entries in sorted(values.items()):
        grouped: dict[tuple[int, int, str | None, int | str], set[str]] = defaultdict(
            set
        )
        for entry in entries:
            grouped[
                (
                    entry.area_id,
                    entry.map_index,
                    entry.season,
                    entry.encounter_route_key,
                )
            ].update(entry.versions)
        result[header_id] = tuple(
            sorted(
                (
                    LocationEncounterReference(
                        header_id=header_id,
                        area_id=area_id,
                        map_index=map_index,
                        season=season,
                        encounter_route_key=route_key,
                        versions=tuple(sorted(versions)),
                    )
                    for (
                        area_id,
                        map_index,
                        season,
                        route_key,
                    ), versions in grouped.items()
                ),
                key=_location_sort_key,
            )
        )
    return result


def _freeze_encounter_locations(
    locations: list[dict[str, Any]],
    location_encounters: Mapping[int, tuple[LocationEncounterReference, ...]],
) -> dict[int | str, tuple[EncounterLocationReference, ...]]:
    location_details = {
        location["header_id"]: (
            _location_display_name(location),
            location.get("section_name"),
        )
        for location in locations
    }
    values: dict[int | str, list[EncounterLocationReference]] = defaultdict(list)
    for header_id, encounters in location_encounters.items():
        details = location_details.get(header_id)
        if details is None:
            # No locations dataset was supplied for this build (build
            # encounters supports that); without a location record there's
            # no display name to attach, so these encounters just don't get
            # a location cross-reference rather than crashing the build.
            continue
        location_name, section_name = details
        for encounter in encounters:
            values[encounter.encounter_route_key].append(
                EncounterLocationReference(
                    encounter_route_key=encounter.encounter_route_key,
                    header_id=header_id,
                    location_name=location_name,
                    section_name=section_name,
                    versions=encounter.versions,
                )
            )

    result = {}
    for route_key, entries in sorted(values.items(), key=lambda item: str(item[0])):
        grouped: dict[tuple[int, str, str | None], set[str]] = defaultdict(set)
        for entry in entries:
            grouped[(entry.header_id, entry.location_name, entry.section_name)].update(
                entry.versions
            )
        result[route_key] = tuple(
            EncounterLocationReference(
                encounter_route_key=route_key,
                header_id=header_id,
                location_name=location_name,
                section_name=section_name,
                versions=tuple(sorted(versions)),
            )
            for (header_id, location_name, section_name), versions in sorted(
                grouped.items(),
                key=lambda item: (item[0][1], item[0][2] or "", item[0][0]),
            )
        )
    return result


def _location_sort_key(value: LocationEncounterReference) -> tuple[Any, ...]:
    return value.area_id, value.season or "", value.versions
