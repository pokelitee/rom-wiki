from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ShardCosts:
    red: int
    blue: int
    yellow: int
    green: int


@dataclass(frozen=True, slots=True)
class TutorMove:
    tutor_id: int
    move_id: int
    shard_costs: ShardCosts
    location_id: int
    table_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TutorCompatibility:
    personal_member: int
    tutor_ids: tuple[int, ...]
    table_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SpecialTutorMove:
    tutor_id: int
    move_id: int
    location_name: str
    eligibility_kind: str
    eligibility_value: int | tuple[int, ...]
    minimum_friendship: int
    script_member: int
    command_offset: int
    map_header_id: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
