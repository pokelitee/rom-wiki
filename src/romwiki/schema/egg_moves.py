from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class OverlayEggMoveSet:
    species_id: int
    move_ids: tuple[int, ...]
    table_index: int
    overlay_offset: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArchiveEggMoveSet:
    species_id: int
    move_ids: tuple[int, ...]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
