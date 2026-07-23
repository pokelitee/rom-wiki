from __future__ import annotations

import struct

from romwiki.schema import (
    EncounterMethod,
    Gen4EncounterArea,
    RecordProvenance,
    WalkingEncounterSlot,
    WaterEncounterSlot,
)
from romwiki.util.errors import InvalidRomError

ENCOUNTER_RECORD_SIZES = (380, 424)
DUAL_SLOT_GAMES = ("ruby", "sapphire", "emerald", "fire-red", "leaf-green")

# Fixed per-slot encounter-chance weights (percent) for the Generation III/IV
# wild-encounter engine. These are not stored in the ROM's encounter tables —
# only each slot's species and level(s) are ROM data — the percentages are
# fixed logic in the game's RNG selection routine and are identical across
# every Gen III/IV game. Publicly documented (e.g. Bulbapedia's "Wild
# Pokémon" article) rather than ROM- or PokéDB-sourced.
GEN4_WALKING_SLOT_CHANCES = (20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1)
GEN4_WATER_SLOT_CHANCES = (60, 30, 5, 4, 1)
GEN4_FISHING_SLOT_CHANCES = (40, 40, 15, 4, 1)


def parse_encounter_record(
    data: bytes,
    *,
    area_id: int,
    archive_path: str,
) -> Gen4EncounterArea:
    if len(data) not in ENCOUNTER_RECORD_SIZES:
        expected = " or ".join(str(size) for size in ENCOUNTER_RECORD_SIZES)
        raise InvalidRomError(
            f"Gen IV encounter record {area_id} has size {len(data)}, "
            f"expected {expected}"
        )

    walking_slots = tuple(
        WalkingEncounterSlot(
            level=_uint32(data, 4 + index * 8),
            species_id=_uint32(data, 8 + index * 8),
        )
        for index in range(12)
    )
    dual_slot_values = struct.unpack_from("<10I", data, 0xA4)
    return Gen4EncounterArea(
        area_id=area_id,
        walking_rate=_uint32(data, 0),
        walking_slots=walking_slots,
        swarm_species_ids=_pair(data, 0x64),
        day_species_ids=_pair(data, 0x6C),
        night_species_ids=_pair(data, 0x74),
        radar_species_ids=struct.unpack_from("<4I", data, 0x7C),
        form_species_ids=struct.unpack_from("<5I", data, 0x8C),
        unknown_value=_uint32(data, 0xA0),
        dual_slot_species_ids={
            game: (dual_slot_values[index * 2], dual_slot_values[index * 2 + 1])
            for index, game in enumerate(DUAL_SLOT_GAMES)
        },
        surf=_parse_water_method(data, 0xCC),
        old_rod=_parse_water_method(data, 0x124),
        good_rod=_parse_water_method(data, 0x150),
        super_rod=(
            _parse_water_method(data, 0x17C)
            if len(data) == ENCOUNTER_RECORD_SIZES[1]
            else EncounterMethod(rate=0, slots=())
        ),
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=area_id,
        ),
    )


def _parse_water_method(data: bytes, offset: int) -> EncounterMethod:
    rate = _uint32(data, offset)
    slots = []
    for index in range(5):
        slot_offset = offset + 4 + index * 8
        maximum_level, minimum_level = struct.unpack_from("<BB", data, slot_offset)
        slots.append(
            WaterEncounterSlot(
                minimum_level=minimum_level,
                maximum_level=maximum_level,
                species_id=_uint32(data, slot_offset + 4),
            )
        )
    return EncounterMethod(rate=rate, slots=tuple(slots))


def _uint32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _pair(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<2I", data, offset)
