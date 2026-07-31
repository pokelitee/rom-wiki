from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class EvolutionEntry:
    method_id: int
    parameter: int
    target_species_id: int


@dataclass(frozen=True, slots=True)
class EvolutionSet:
    species_id: int
    evolutions: tuple[EvolutionEntry, ...]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
