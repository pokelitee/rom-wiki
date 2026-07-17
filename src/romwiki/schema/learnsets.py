from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class LevelUpMove:
    level: int
    move_id: int


@dataclass(frozen=True, slots=True)
class Gen4LevelUpLearnset:
    species_id: int
    moves: tuple[LevelUpMove, ...]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
