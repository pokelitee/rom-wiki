from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.schema import RecordProvenance
from romwiki.util.errors import InvalidRomError

# Engine-defined area IDs; the encounter archive stores the ID order but no text.
SAFARI_AREA_NAMES = (
    "Plains",
    "Meadow",
    "Savannah",
    "Peak",
    "Rocky Beach",
    "Wetland",
    "Forest",
    "Swamp",
    "Marshland",
    "Wasteland",
    "Mountain",
    "Desert",
)
SAFARI_METHODS = ("grass", "surf", "old-rod", "good-rod", "super-rod")
SAFARI_TIMES = ("morning", "day", "night")
SAFARI_BLOCK_TYPES = (None, "plains", "forest", "peak", "waterside")
SAFARI_BASE_SLOT_COUNT = 10
SAFARI_HEADER_SIZE = 8


@dataclass(frozen=True, slots=True)
class SafariSlot:
    species_id: int
    level: int


@dataclass(frozen=True, slots=True)
class SafariBlockRequirement:
    block_type: str
    count: int


@dataclass(frozen=True, slots=True)
class SafariBlockEncounter:
    index: int
    requirements: tuple[SafariBlockRequirement, ...]
    times: dict[str, SafariSlot]


@dataclass(frozen=True, slots=True)
class SafariMethod:
    base_pools: dict[str, tuple[SafariSlot, ...]]
    block_encounters: tuple[SafariBlockEncounter, ...]


@dataclass(frozen=True, slots=True)
class SafariEncounter:
    safari_area_id: int
    area_name: str
    methods: dict[str, SafariMethod]
    provenance: RecordProvenance


def parse_safari_encounter_record(
    data: bytes,
    *,
    safari_area_id: int,
    archive_path: str,
    species_count: int,
) -> SafariEncounter:
    if not 0 <= safari_area_id < len(SAFARI_AREA_NAMES):
        raise InvalidRomError(f"Invalid Safari Zone area ID {safari_area_id}")
    if len(data) < SAFARI_HEADER_SIZE:
        raise InvalidRomError(f"Safari Zone member {safari_area_id} is truncated")
    block_counts = data[: len(SAFARI_METHODS)]
    if any(value > SAFARI_BASE_SLOT_COUNT for value in block_counts):
        raise InvalidRomError(
            f"Safari Zone member {safari_area_id} has an invalid block slot count"
        )
    if any(data[len(SAFARI_METHODS) : SAFARI_HEADER_SIZE]):
        raise InvalidRomError(
            f"Safari Zone member {safari_area_id} has nonzero header padding"
        )
    expected_size = SAFARI_HEADER_SIZE + sum(
        SAFARI_BASE_SLOT_COUNT * len(SAFARI_TIMES) * 4 + count * 16
        for count in block_counts
    )
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Safari Zone member {safari_area_id} has size {len(data)}, expected "
            f"{expected_size}"
        )

    cursor = SAFARI_HEADER_SIZE
    methods = {}
    for method_name, block_count in zip(SAFARI_METHODS, block_counts, strict=True):
        base_pools = {}
        for time_name in SAFARI_TIMES:
            slots, cursor = _parse_slots(
                data,
                cursor,
                SAFARI_BASE_SLOT_COUNT,
                safari_area_id=safari_area_id,
                species_count=species_count,
            )
            base_pools[time_name] = slots

        block_slots_by_time = []
        for _time_name in SAFARI_TIMES:
            slots, cursor = _parse_slots(
                data,
                cursor,
                block_count,
                safari_area_id=safari_area_id,
                species_count=species_count,
            )
            block_slots_by_time.append(slots)

        requirements = []
        for block_index in range(block_count):
            raw = struct.unpack_from("<4B", data, cursor)
            cursor += 4
            parsed = []
            for requirement_index in range(2):
                start = requirement_index * 2
                block_type_id, count = raw[start : start + 2]
                if block_type_id >= len(SAFARI_BLOCK_TYPES):
                    raise InvalidRomError(
                        f"Safari Zone member {safari_area_id} block encounter "
                        f"{block_index} has invalid block type {block_type_id}"
                    )
                block_type = SAFARI_BLOCK_TYPES[block_type_id]
                if (block_type is None) != (count == 0):
                    raise InvalidRomError(
                        f"Safari Zone member {safari_area_id} block encounter "
                        f"{block_index} has an invalid block requirement"
                    )
                if block_type is not None:
                    parsed.append(SafariBlockRequirement(block_type, count))
            if len(parsed) == 2 and parsed[0].block_type == parsed[1].block_type:
                raise InvalidRomError(
                    f"Safari Zone member {safari_area_id} block encounter "
                    f"{block_index} repeats a block type"
                )
            requirements.append(tuple(parsed))

        methods[method_name] = SafariMethod(
            base_pools=base_pools,
            block_encounters=tuple(
                SafariBlockEncounter(
                    index=index,
                    requirements=requirements[index],
                    times={
                        time_name: block_slots_by_time[time_index][index]
                        for time_index, time_name in enumerate(SAFARI_TIMES)
                    },
                )
                for index in range(block_count)
            ),
        )
    assert cursor == len(data)
    return SafariEncounter(
        safari_area_id=safari_area_id,
        area_name=SAFARI_AREA_NAMES[safari_area_id],
        methods=methods,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=safari_area_id
        ),
    )


def _parse_slots(
    data: bytes,
    cursor: int,
    count: int,
    *,
    safari_area_id: int,
    species_count: int,
) -> tuple[tuple[SafariSlot, ...], int]:
    slots = []
    for _ in range(count):
        species_id, level, padding = struct.unpack_from("<HBB", data, cursor)
        cursor += 4
        if not 0 < species_id < species_count:
            raise InvalidRomError(
                f"Safari Zone member {safari_area_id} references invalid species "
                f"{species_id}"
            )
        if not 0 < level <= 100:
            raise InvalidRomError(
                f"Safari Zone member {safari_area_id} has invalid level {level}"
            )
        if padding:
            raise InvalidRomError(
                f"Safari Zone member {safari_area_id} has nonzero slot padding"
            )
        slots.append(SafariSlot(species_id, level))
    return tuple(slots), cursor


__all__ = [
    "SAFARI_AREA_NAMES",
    "SAFARI_BASE_SLOT_COUNT",
    "SAFARI_BLOCK_TYPES",
    "SAFARI_METHODS",
    "SAFARI_TIMES",
    "SafariBlockEncounter",
    "SafariBlockRequirement",
    "SafariEncounter",
    "SafariMethod",
    "SafariSlot",
    "parse_safari_encounter_record",
]
