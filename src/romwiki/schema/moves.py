from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class Move:
    move_id: int
    effect_id: int
    damage_class_id: int
    power: int
    type_id: int
    accuracy: int
    pp: int
    effect_chance: int
    target_id: int
    priority: int
    flags: int
    provenance: RecordProvenance
    contest_effect_id: int | None = None
    contest_type_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.contest_effect_id is None:
            result.pop("contest_effect_id")
        if self.contest_type_id is None:
            result.pop("contest_type_id")
        return result
