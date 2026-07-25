from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class Gen4PickupTables:
    common_item_ids: tuple[int, ...]
    rare_item_ids: tuple[int, ...]
    common_rate: tuple[int, ...]
    honey_gather_rate: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Gen5PickupTable:
    # The 29-word table found by byte-pattern search in the Battle overlay
    # (`PickupOvlNumber`) -- unlike Generation IV's separate common/rare item
    # lists, this generation packs every level range's items into one shared,
    # sliding-window array (see `gen5_bw/pickup.py`).
    item_ids: tuple[int, ...]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
