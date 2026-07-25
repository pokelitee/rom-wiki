from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class Gen5NpcTrade:
    trade_id: int
    nickname: str
    ot_name: str
    ot_id: int
    offered_species_id: int
    requested_species_id: int
    held_item_id: int | None
    # Raw ROM storage order -- matches Generation IV's identical-shaped
    # record (hp, atk, def, speed, spatk, spdef), but that specific per-stat
    # mapping hasn't been independently re-verified for this generation, so
    # it's kept as a plain tuple rather than labeled per stat.
    ivs: tuple[int, int, int, int, int, int]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
