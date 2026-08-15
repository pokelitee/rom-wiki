from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.schema import RecordProvenance
from romwiki.util.errors import InvalidRomError

HEADBUTT_SLOT_CHANCES = (50, 15, 15, 10, 5, 5)
HEADBUTT_SLOT_COUNT = 6
HEADBUTT_POOL_COUNT = 3
HEADBUTT_HEADER_SIZE = 4
HEADBUTT_SLOT_SIZE = 4
HEADBUTT_COORDS_PER_GROUP = 6


@dataclass(frozen=True, slots=True)
class HeadbuttSlot:
    species_id: int
    minimum_level: int
    maximum_level: int
    chance: int


@dataclass(frozen=True, slots=True)
class HeadbuttTreeGroup:
    group: int
    kind: str
    coordinates: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class HeadbuttEncounter:
    header_id: int
    pools: dict[str, tuple[HeadbuttSlot, ...]]
    tree_groups: tuple[HeadbuttTreeGroup, ...]
    provenance: RecordProvenance


def parse_headbutt_record(
    data: bytes,
    *,
    header_id: int,
    archive_path: str,
    species_count: int,
) -> HeadbuttEncounter | None:
    if len(data) < HEADBUTT_HEADER_SIZE:
        raise InvalidRomError(f"Headbutt member {header_id} is truncated")
    regular_count, secret_count = struct.unpack_from("<2H", data)
    if regular_count == 0 and secret_count == 0:
        if len(data) != HEADBUTT_HEADER_SIZE:
            raise InvalidRomError(
                f"Empty Headbutt member {header_id} has trailing data"
            )
        return None

    slots_size = HEADBUTT_POOL_COUNT * HEADBUTT_SLOT_COUNT * HEADBUTT_SLOT_SIZE
    coordinate_count = (regular_count + secret_count) * HEADBUTT_COORDS_PER_GROUP
    expected_size = HEADBUTT_HEADER_SIZE + slots_size + coordinate_count * 4
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Headbutt member {header_id} has size {len(data)}, expected "
            f"{expected_size}"
        )

    pools = {}
    for pool_index, kind in enumerate(("common", "rare", "secret")):
        slots = []
        pool_active = secret_count > 0 if kind == "secret" else regular_count > 0
        for slot_index, chance in enumerate(HEADBUTT_SLOT_CHANCES):
            offset = (
                HEADBUTT_HEADER_SIZE
                + (pool_index * HEADBUTT_SLOT_COUNT + slot_index) * HEADBUTT_SLOT_SIZE
            )
            species_id, minimum_level, maximum_level = struct.unpack_from(
                "<HBB", data, offset
            )
            if not pool_active:
                if species_id or minimum_level or maximum_level:
                    raise InvalidRomError(
                        f"Headbutt member {header_id} has data in unused {kind} pool"
                    )
                continue
            if not 0 < species_id < species_count:
                raise InvalidRomError(
                    f"Headbutt member {header_id} references invalid species "
                    f"{species_id}"
                )
            if not 0 < minimum_level <= maximum_level <= 100:
                raise InvalidRomError(
                    f"Headbutt member {header_id} has invalid level range "
                    f"{minimum_level}-{maximum_level}"
                )
            slots.append(
                HeadbuttSlot(
                    species_id=species_id,
                    minimum_level=minimum_level,
                    maximum_level=maximum_level,
                    chance=chance,
                )
            )
        pools[kind] = tuple(slots)

    coordinate_offset = HEADBUTT_HEADER_SIZE + slots_size
    coordinates = tuple(
        struct.unpack_from("<2h", data, coordinate_offset + index * 4)
        for index in range(coordinate_count)
    )
    groups = []
    for index in range(regular_count + secret_count):
        start = index * HEADBUTT_COORDS_PER_GROUP
        raw_coordinates = coordinates[start : start + HEADBUTT_COORDS_PER_GROUP]
        try:
            terminator = raw_coordinates.index((-1, -1))
        except ValueError:
            group_coordinates = raw_coordinates
        else:
            if any(value != (-1, -1) for value in raw_coordinates[terminator:]):
                raise InvalidRomError(
                    f"Headbutt member {header_id} group {index} has coordinates "
                    "after its terminator"
                )
            group_coordinates = raw_coordinates[:terminator]
        if not group_coordinates:
            raise InvalidRomError(
                f"Headbutt member {header_id} group {index} has no coordinates"
            )
        groups.append(
            HeadbuttTreeGroup(
                group=index,
                kind="regular" if index < regular_count else "secret",
                coordinates=group_coordinates,
            )
        )
    return HeadbuttEncounter(
        header_id=header_id,
        pools=pools,
        tree_groups=tuple(groups),
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=header_id
        ),
    )


__all__ = [
    "HEADBUTT_SLOT_CHANCES",
    "HeadbuttEncounter",
    "HeadbuttSlot",
    "HeadbuttTreeGroup",
    "parse_headbutt_record",
]
