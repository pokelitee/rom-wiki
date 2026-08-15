from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def encounter_route_key(record: Mapping[str, Any]) -> int | str:
    """Return the stable rendered identity for an encounter area."""
    grotto_id = record.get("grotto_id")
    if record.get("source_type") == "hidden-grotto" and isinstance(grotto_id, int):
        return f"hidden-grotto-{grotto_id:02}"
    header_id = record.get("header_id")
    if record.get("source_type") == "daily-swarm" and isinstance(header_id, int):
        return f"daily-swarm-{header_id:03}"
    if record.get("source_type") == "headbutt" and isinstance(header_id, int):
        return f"headbutt-{header_id:03}"
    map_index = record.get("map_index")
    if not isinstance(map_index, int):
        return int(record["area_id"])
    return f"map-{map_index:03}"
