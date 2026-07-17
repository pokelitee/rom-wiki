from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Gen4EggMoveSet:
    species_id: int
    move_ids: tuple[int, ...]
    table_index: int
    overlay_offset: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
