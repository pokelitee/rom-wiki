from __future__ import annotations

import struct
from dataclasses import asdict, dataclass
from typing import Any

from romwiki.schema import EncounterMethod, RecordProvenance, WalkingEncounterSlot
from romwiki.schema.encounters import WaterEncounterSlot
from romwiki.util.errors import InvalidRomError

HGSS_ENCOUNTER_RECORD_SIZE = 196
HGSS_WALKING_SLOT_CHANCES = (20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1)
HGSS_WATER_SLOT_CHANCES = (60, 30, 5, 4, 1)
HGSS_ROCK_SMASH_SLOT_CHANCES = (80, 20)
HGSS_FISHING_SLOT_CHANCES = (40, 30, 15, 10, 5)


@dataclass(frozen=True, slots=True)
class HGSSEncounterArea:
    area_id: int
    walking_rate: int
    walking_variants: dict[str, tuple[WalkingEncounterSlot, ...]]
    radio_species_ids: tuple[int, int, int, int]
    surf: EncounterMethod
    rock_smash: EncounterMethod
    old_rod: EncounterMethod
    good_rod: EncounterMethod
    super_rod: EncounterMethod
    swarm_species_ids: tuple[int, int]
    night_fishing_species_id: int | None
    fishing_swarm_species_id: int | None
    provenance: RecordProvenance
    locations: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_encounter_record(
    data: bytes, *, area_id: int, archive_path: str
) -> HGSSEncounterArea:
    if len(data) not in {192, HGSS_ENCOUNTER_RECORD_SIZE}:
        raise InvalidRomError(
            f"HGSS encounter record {area_id} has size {len(data)}, "
            f"expected 192 or {HGSS_ENCOUNTER_RECORD_SIZE}"
        )
    rates = data[:6]
    if data[6:8] != b"\0\0":
        raise InvalidRomError(
            f"HGSS encounter record {area_id} has nonzero rate padding"
        )
    levels = data[8:20]
    walking_variants = {
        period: tuple(
            WalkingEncounterSlot(
                level=levels[index],
                species_id=struct.unpack_from("<H", data, offset + index * 2)[0],
            )
            for index in range(12)
        )
        for period, offset in (("morning", 20), ("day", 44), ("night", 68))
    }
    position = 100
    surf = _method(data, position, rates[1], 5)
    position += 20
    rock_smash = _method(data, position, rates[2], 2)
    position += 8
    old_rod = _method(data, position, rates[3], 5)
    position += 20
    good_rod = _method(data, position, rates[4], 5)
    position += 20
    super_rod = _method(data, position, rates[5], 5)
    position += 20
    assert position == 188
    return HGSSEncounterArea(
        area_id=area_id,
        walking_rate=rates[0],
        walking_variants=walking_variants,
        radio_species_ids=struct.unpack_from("<4H", data, 92),
        surf=surf,
        rock_smash=rock_smash,
        old_rod=old_rod,
        good_rod=good_rod,
        super_rod=super_rod,
        swarm_species_ids=struct.unpack_from("<2H", data, position),
        night_fishing_species_id=(
            struct.unpack_from("<H", data, position + 4)[0]
            if len(data) == HGSS_ENCOUNTER_RECORD_SIZE
            else None
        ),
        fishing_swarm_species_id=(
            struct.unpack_from("<H", data, position + 6)[0]
            if len(data) == HGSS_ENCOUNTER_RECORD_SIZE
            else None
        ),
        provenance=RecordProvenance(source="rom", archive=archive_path, member=area_id),
    )


def _method(data: bytes, offset: int, rate: int, count: int) -> EncounterMethod:
    return EncounterMethod(
        rate=rate,
        slots=tuple(
            WaterEncounterSlot(
                minimum_level=data[offset + index * 4],
                maximum_level=data[offset + index * 4 + 1],
                species_id=struct.unpack_from("<H", data, offset + index * 4 + 2)[0],
            )
            for index in range(count)
        ),
    )
