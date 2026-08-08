from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class NpcTrade:
    trade_id: int
    nickname: str
    ot_name: str
    ot_id: int
    offered_species_id: int
    # Undocumented by Gen5RomHandler.java's own `getIngameTrades` (which never
    # reads this field), but confirmed meaningful: Black's inactive "White
    # counterpart" Basculin trade (blue-striped) differs from Black's own
    # active one (red-striped) at this exact offset (0 vs 1) and no other
    # byte in the record besides trade bookkeeping fields -- decoded rather
    # than left as an unknown value.
    offered_forme_id: int
    requested_species_id: int
    held_item_id: int | None
    # Raw ROM storage order. The specific per-stat mapping has not been
    # independently verified for every engine, so
    # it's kept as a plain tuple rather than labeled per stat.
    ivs: tuple[int, int, int, int, int, int]
    provenance: RecordProvenance
    interaction: str = "fixed-location"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
