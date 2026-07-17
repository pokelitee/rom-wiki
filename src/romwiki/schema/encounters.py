from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema.pokemon import RecordProvenance


@dataclass(frozen=True, slots=True)
class WalkingEncounterSlot:
    level: int
    species_id: int


@dataclass(frozen=True, slots=True)
class WaterEncounterSlot:
    minimum_level: int
    maximum_level: int
    species_id: int


@dataclass(frozen=True, slots=True)
class EncounterMethod:
    rate: int
    slots: tuple[WaterEncounterSlot, ...]


@dataclass(frozen=True, slots=True)
class EncounterLocation:
    header_id: int
    internal_name: str
    location_name_id: int
    name: str


@dataclass(frozen=True, slots=True)
class Gen4EncounterArea:
    area_id: int
    walking_rate: int
    walking_slots: tuple[WalkingEncounterSlot, ...]
    swarm_species_ids: tuple[int, int]
    day_species_ids: tuple[int, int]
    night_species_ids: tuple[int, int]
    radar_species_ids: tuple[int, int, int, int]
    form_species_ids: tuple[int, int, int, int, int]
    unknown_value: int
    dual_slot_species_ids: dict[str, tuple[int, int]]
    surf: EncounterMethod
    old_rod: EncounterMethod
    good_rod: EncounterMethod
    super_rod: EncounterMethod
    provenance: RecordProvenance
    locations: tuple[EncounterLocation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
