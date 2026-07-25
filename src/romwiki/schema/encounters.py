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
    # Not species IDs — see engine constant docs for GEN4_UNOWN_FORM_TABLES.
    # Confirmed constant across every Renegade Platinum/Platinum-US encounter
    # record ((100, 100, 0, 0, 0) or (0, 0, 0, 0, 0)); kept as a raw fact
    # rather than dropped since its true purpose isn't fully understood.
    encounter_form_rates: tuple[int, int, int, int, int]
    unown_table_id: int
    dual_slot_species_ids: dict[str, tuple[int, int]]
    surf: EncounterMethod
    old_rod: EncounterMethod
    good_rod: EncounterMethod
    super_rod: EncounterMethod
    provenance: RecordProvenance
    locations: tuple[EncounterLocation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Gen5EncounterSlot:
    species_id: int
    form_id: int
    minimum_level: int
    maximum_level: int


@dataclass(frozen=True, slots=True)
class Gen5EncounterMethod:
    rate: int
    slots: tuple[Gen5EncounterSlot, ...]


@dataclass(frozen=True, slots=True)
class Gen5EncounterArea:
    area_id: int
    map_index: int
    season: str | None
    grass_cave: Gen5EncounterMethod
    doubles_grass: Gen5EncounterMethod
    shaking_spots: Gen5EncounterMethod
    surfing: Gen5EncounterMethod
    surfing_spots: Gen5EncounterMethod
    fishing: Gen5EncounterMethod
    fishing_spots: Gen5EncounterMethod
    provenance: RecordProvenance
    locations: tuple[EncounterLocation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
