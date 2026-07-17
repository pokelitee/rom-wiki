from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class Gen4Move:
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
    contest_effect_id: int
    contest_type_id: int
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
