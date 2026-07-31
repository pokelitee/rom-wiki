from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class StaticEncounter:
    encounter_id: int
    species_id: int
    # None for gift-egg encounters (e.g. Larvesta), which have no stored
    # level -- the egg hatches at level 1 like any other.
    level: int | None
    is_egg: bool
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
