from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Machine:
    machine_id: int
    kind: str
    number: int
    move_id: int
    table_index: int
    item_id: int

    @property
    def name(self) -> str:
        return f"{self.kind.upper()}{self.number:02}"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "name": self.name}
