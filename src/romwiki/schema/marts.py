from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class Gen5Shop:
    shop_id: int
    name: str
    kind: str
    is_main_game: bool
    item_ids: tuple[int, ...]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
