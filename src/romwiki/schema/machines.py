from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Gen4Machine:
    machine_id: int
    kind: str
    number: int
    move_id: int
    table_index: int

    @property
    def name(self) -> str:
        return f"{self.kind.upper()}{self.number:02}"

    @property
    def item_id(self) -> int:
        """The Gen IV item table ID for this machine's item.

        TM01-TM92 and HM01-HM08 occupy a fixed, contiguous block of item IDs
        (328-427) in every Gen IV game, in the same order as ``machine_id``.
        This layout is engine data, not ROM-hack-mutable, so it can be
        derived rather than read per-ROM.
        """
        return self.machine_id + 327

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "name": self.name, "item_id": self.item_id}
