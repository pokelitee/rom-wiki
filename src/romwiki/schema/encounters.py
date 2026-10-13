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
class ConditionalEncounterArea:
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
class MethodEncounterArea:
    """Generation III's wild-encounter shape: up to four independent
    methods (land/water/rock-smash/fishing) per map, each an explicit
    min/max level range per slot -- no season system, no swarm/day/night/
    radar/dual-slot/Unown bonus-slot mechanics (those are Generation IV/V
    additions). Reuses `WaterEncounterSlot`/`EncounterMethod` as-is since
    Generation III stores an explicit level range for every method,
    including land (unlike Generation IV's land encounters, which store one
    exact level via `WalkingEncounterSlot`).
    """

    area_id: int
    map_group: int
    map_num: int
    land: EncounterMethod | None
    water: EncounterMethod | None
    rock_smash: EncounterMethod | None
    fishing: EncounterMethod | None
    provenance: RecordProvenance
    locations: tuple[EncounterLocation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SeasonalEncounterSlot:
    species_id: int
    form_id: int
    minimum_level: int
    maximum_level: int


@dataclass(frozen=True, slots=True)
class SeasonalEncounterMethod:
    rate: int
    slots: tuple[SeasonalEncounterSlot, ...]


@dataclass(frozen=True, slots=True)
class SeasonalEncounterArea:
    area_id: int
    map_index: int
    season: str | None
    grass_cave: SeasonalEncounterMethod
    doubles_grass: SeasonalEncounterMethod
    shaking_spots: SeasonalEncounterMethod
    surfing: SeasonalEncounterMethod
    surfing_spots: SeasonalEncounterMethod
    fishing: SeasonalEncounterMethod
    fishing_spots: SeasonalEncounterMethod
    provenance: RecordProvenance
    location_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
