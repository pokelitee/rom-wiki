"""Trainer-variant resolution helpers shared byte-for-byte by DPPT and HGSS.

Both engines' `battle_variants.py` independently declared identical copies
of these two functions; hoisted here so a future fix to either only needs to
land once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def resolved_battle_location(
    records_by_id: Mapping[int, Mapping[str, Any]], trainer_ids: Sequence[int]
) -> str | None:
    """Return the map name every variant in a group resolves to, if they agree.

    Disagreement means the group does not describe one battle site, so the
    fallback label is used rather than picking one variant's map.
    """
    names = set()
    for trainer_id in trainer_ids:
        record = records_by_id.get(trainer_id)
        if record is None:
            return None
        places = record.get("script_references") or record.get("locations") or ()
        if not places:
            return None
        name = places[0].get("name")
        if not name:
            return None
        names.add(name)
    return names.pop() if len(names) == 1 else None


def species_name(species_names: Any, species_id: int) -> str:
    """Name a species from this profile's own name table, indexed or mapped."""
    if isinstance(species_names, Mapping):
        name = species_names.get(species_id)
    elif 0 <= species_id < len(species_names):
        name = species_names[species_id]
    else:
        name = None
    return name.title() if name else f"species-{species_id}"
