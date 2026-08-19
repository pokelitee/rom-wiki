from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class EncounterSourceType(StrEnum):
    """Normalized identities for nonstandard encounter sources."""

    DAILY_SWARM = "daily-swarm"
    HEADBUTT = "headbutt"
    HIDDEN_GROTTO = "hidden-grotto"
    SAFARI_ZONE = "safari-zone"


MAP_OWNED_CONDITIONAL_SOURCES = frozenset(
    {
        EncounterSourceType.DAILY_SWARM,
        EncounterSourceType.HEADBUTT,
        EncounterSourceType.HIDDEN_GROTTO,
    }
)
CONDITIONAL_ENCOUNTER_SOURCES = frozenset(EncounterSourceType)
DAILY_SWARM_ANCHOR = "daily-swarm"
HEADBUTT_ANCHOR = "headbutt-encounters"
HIDDEN_GROTTO_ANCHOR_PREFIX = "hidden-grotto"
SAFARI_ZONE_ROUTE = "safari-zone"


def hidden_grotto_anchor(grotto_id: int) -> str:
    return f"{HIDDEN_GROTTO_ANCHOR_PREFIX}-{grotto_id:02}"


def conditional_encounter_key(record: Mapping[str, Any]) -> str:
    """Return the stable catalog identity for a conditional encounter source."""
    source_type = record.get("source_type")
    if source_type == EncounterSourceType.HIDDEN_GROTTO:
        return hidden_grotto_anchor(_required_int(record, "grotto_id"))
    if source_type == EncounterSourceType.DAILY_SWARM:
        return f"{DAILY_SWARM_ANCHOR}-{_required_location_header_id(record):03}"
    if source_type == EncounterSourceType.HEADBUTT:
        return f"headbutt-{_required_location_header_id(record):03}"
    if source_type == EncounterSourceType.SAFARI_ZONE:
        return f"{SAFARI_ZONE_ROUTE}-{_required_int(record, 'safari_area_id'):02}"
    raise ValueError(f"Unsupported conditional encounter source: {source_type!r}")


def _required_int(record: Mapping[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Conditional encounter {key} must be an integer")
    return value


def _required_location_header_id(record: Mapping[str, Any]) -> int:
    """Read a conditional encounter's owning map header ID.

    Every map-owned conditional source (grotto/swarm/headbutt) nests
    `header_id` under the record's own `location`, the same place
    `extraction/encounters.py`'s `_extract_hidden_grottos`/`_extract_swarms`/
    headbutt extraction put it -- never as a top-level `header_id` field.
    """
    location = record.get("location")
    if not isinstance(location, Mapping):
        raise ValueError("Conditional encounter is missing its location")
    return _required_int(location, "header_id")


def encounter_route_key(record: Mapping[str, Any]) -> int | str:
    """Return the stable rendered identity for an encounter area.

    Conditional sources (grotto/swarm/headbutt/safari) validate their
    required fields the same way `conditional_encounter_key` does: a
    matching `source_type` with a missing or malformed field raises rather
    than silently falling through to the generic `map_index`/`area_id`
    identity below, which would otherwise produce a route key inconsistent
    with the catalog identity `conditional_encounter_key` computed for the
    same record.
    """
    source_type = record.get("source_type")
    if source_type == EncounterSourceType.HIDDEN_GROTTO:
        grotto_id = _required_int(record, "grotto_id")
        header_id = _required_location_header_id(record)
        return f"header-{header_id:03}#{hidden_grotto_anchor(grotto_id)}"
    if source_type == EncounterSourceType.DAILY_SWARM:
        header_id = _required_location_header_id(record)
        return f"header-{header_id:03}#{DAILY_SWARM_ANCHOR}"
    if source_type == EncounterSourceType.HEADBUTT:
        header_id = _required_location_header_id(record)
        return f"header-{header_id:03}#{HEADBUTT_ANCHOR}"
    if source_type == EncounterSourceType.SAFARI_ZONE:
        # Each Safari area now renders its own page (see encounters.py's
        # per-area rendering, split out to keep the combined page under the
        # site audit's page-size limit), so its render identity is the same
        # per-area catalog identity rather than an anchor into a shared page.
        return conditional_encounter_key(record)
    map_index = record.get("map_index")
    if not isinstance(map_index, int):
        return int(record["area_id"])
    return f"map-{map_index:03}"
