from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from romwiki.util.text import name_slug


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
        return f"{DAILY_SWARM_ANCHOR}-{_required_int(record, 'header_id'):03}"
    if source_type == EncounterSourceType.HEADBUTT:
        return f"headbutt-{_required_int(record, 'header_id'):03}"
    if source_type == EncounterSourceType.SAFARI_ZONE:
        return f"{SAFARI_ZONE_ROUTE}-{_required_int(record, 'safari_area_id'):02}"
    raise ValueError(f"Unsupported conditional encounter source: {source_type!r}")


def _required_int(record: Mapping[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Conditional encounter {key} must be an integer")
    return value


def encounter_route_key(record: Mapping[str, Any]) -> int | str:
    """Return the stable rendered identity for an encounter area."""
    grotto_id = record.get("grotto_id")
    if record.get("source_type") == EncounterSourceType.HIDDEN_GROTTO and isinstance(
        grotto_id, int
    ):
        location = record.get("location")
        header_id = location.get("header_id") if isinstance(location, Mapping) else None
        if isinstance(header_id, int):
            return f"header-{header_id:03}#{hidden_grotto_anchor(grotto_id)}"
    header_id = record.get("header_id")
    if record.get("source_type") == EncounterSourceType.DAILY_SWARM and isinstance(
        header_id, int
    ):
        return f"header-{header_id:03}#{DAILY_SWARM_ANCHOR}"
    if record.get("source_type") == EncounterSourceType.HEADBUTT and isinstance(
        header_id, int
    ):
        return f"header-{header_id:03}#{HEADBUTT_ANCHOR}"
    safari_area_id = record.get("safari_area_id")
    if record.get("source_type") == EncounterSourceType.SAFARI_ZONE and isinstance(
        safari_area_id, int
    ):
        area_name = record.get("area_name")
        if isinstance(area_name, str):
            return f"{SAFARI_ZONE_ROUTE}#{name_slug(area_name)}"
    map_index = record.get("map_index")
    if not isinstance(map_index, int):
        return int(record["area_id"])
    return f"map-{map_index:03}"
