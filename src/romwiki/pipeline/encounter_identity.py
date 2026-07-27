from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def encounter_route_key(record: Mapping[str, Any]) -> int | str:
    """Return the stable rendered identity for an encounter-area variant."""
    map_index = record.get("map_index")
    if not isinstance(map_index, int):
        return int(record["area_id"])
    season = record.get("season")
    return (
        f"map-{map_index:03}-{season}"
        if isinstance(season, str) and season
        else f"map-{map_index:03}"
    )
