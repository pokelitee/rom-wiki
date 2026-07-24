from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StatBlock:
    hp: int
    attack: int
    defense: int
    speed: int
    special_attack: int
    special_defense: int


@dataclass(frozen=True, slots=True)
class WildHeldItems:
    common: int
    rare: int


@dataclass(frozen=True, slots=True)
class RecordProvenance:
    source: str
    archive: str
    member: int


@dataclass(frozen=True, slots=True)
class PokemonPersonalData:
    species_id: int
    base_stats: StatBlock
    type_ids: tuple[int, int]
    catch_rate: int
    base_experience: int
    ev_yields: StatBlock
    wild_held_items: WildHeldItems
    gender_ratio: int
    hatch_cycles: int
    base_friendship: int
    growth_rate_id: int
    egg_group_ids: tuple[int, int]
    ability_ids: tuple[int, ...]
    safari_flee_rate: int
    body_color_id: int
    flip_sprite: bool
    machine_ids: tuple[int, ...]
    machine_masks: tuple[int, int, int, int]
    provenance: RecordProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
