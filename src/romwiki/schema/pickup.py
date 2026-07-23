from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Gen4PickupTables:
    common_item_ids: tuple[int, ...]
    rare_item_ids: tuple[int, ...]
    common_rate: tuple[int, ...]
    honey_gather_rate: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
