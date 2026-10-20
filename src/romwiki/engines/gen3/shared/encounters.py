from __future__ import annotations

import struct
from collections.abc import Callable

from romwiki.schema import (
    EncounterMethod,
    MethodEncounterArea,
    RecordProvenance,
    WaterEncounterSlot,
)
from romwiki.util.errors import InvalidRomError

from .constants import (
    ENCOUNTER_HEADER_SIZE,
    ENCOUNTER_METHOD_NAMES,
    MAX_MAP_GROUPS,
    MAX_MAPS_PER_GROUP,
)

# `MAP_GROUP(MAP_UNDEFINED)`, the map group of the header that ends the table.
_END_MAP_GROUP = 0xFF

# Generation III's wild-encounter tables (`gWildMonHeaders` in the public
# pokefirered/pokeemerald decompilations), verified against the real
# FireRed, LeafGreen, and Emerald ROMs by decoding each game's own table to
# real, sane species (see `constants.py`'s `ENCOUNTER_HEADER_SIZE` comment
# for the specific cross-checks). Struct shapes below are proven identical
# across all three games; only each profile's table offset/count differ.
#
# `WildPokemonHeader` (20 bytes, one per map):
#   0x00  mapGroup (u8)
#   0x01  mapNum (u8)
#   0x02-0x03  padding
#   0x04  landMonsInfo pointer (u32 GBA ROM address, or 0 if absent)
#   0x08  waterMonsInfo pointer
#   0x0C  rockSmashMonsInfo pointer
#   0x10  fishingMonsInfo pointer
#
# Each non-null method pointer resolves (via `pointers.resolve_gba_pointer`,
# done by the extraction layer since it owns ROM I/O) to an 8-byte
# `WildPokemonInfo` struct -- NOT the slot array inline, a second level of
# pointer indirection not present in any other domain implemented so far:
#   0x00  rate (u8)
#   0x01-0x03  padding
#   0x04  wildPokemon slots pointer (u32 GBA ROM address)
#
# That second pointer resolves to a fixed-count array of 4-byte slots:
#   0x00  minLevel (u8)
#   0x01  maxLevel (u8)
#   0x02  species (u16 LE)
# Slot counts are fixed per method (verified, not ROM-derived): land 12,
# water 5, rock-smash 5, fishing 10 (old/good/super rod concatenated into
# one table, unlike Generation IV+'s three separate per-rod methods) --
# see `constants.py`'s ENCOUNTER_*_SLOT_COUNT constants.
_HEADER_METHOD_POINTER_OFFSETS = {
    "land": 0x04,
    "water": 0x08,
    "rock_smash": 0x0C,
    "fishing": 0x10,
}
_INFO_SIZE = 8
_SLOT_SIZE = 4


def parse_header(data: bytes, *, map_index: int) -> tuple[int, int, dict[str, int]]:
    """Decode a 20-byte `WildPokemonHeader`.

    Returns `(map_group, map_num, pointers)`, where `pointers` maps each
    method name in `constants.ENCOUNTER_METHOD_NAMES` to its raw GBA ROM
    pointer (0 if that method is absent on this map) -- resolving those
    pointers to file offsets is the extraction layer's job, since it owns
    ROM I/O.
    """
    if len(data) != ENCOUNTER_HEADER_SIZE:
        raise InvalidRomError(
            f"Gen III encounter header {map_index} has size {len(data)}, "
            f"expected {ENCOUNTER_HEADER_SIZE}"
        )
    map_group, map_num = data[0], data[1]
    pointers = {
        name: struct.unpack_from("<I", data, offset)[0]
        for name, offset in _HEADER_METHOD_POINTER_OFFSETS.items()
    }
    return map_group, map_num, pointers


def count_encounter_headers(read: Callable[[int, int], bytes], offset: int) -> int:
    """Count the `WildPokemonHeader`s in the table at `offset`.

    The ROM stores no count: the table ends at the first header whose map
    group is 0xFF, and a hack that adds maps extends it up to the same
    terminator. `read(offset, size)` returns ROM bytes.
    """
    for index in range(MAX_MAP_GROUPS * MAX_MAPS_PER_GROUP):
        if read(offset + index * ENCOUNTER_HEADER_SIZE, 1)[0] == _END_MAP_GROUP:
            return index
    raise InvalidRomError("Gen III encounter table has no terminating header")


def parse_method_info(data: bytes, *, map_index: int, name: str) -> tuple[int, int]:
    """Decode an 8-byte `WildPokemonInfo` struct into `(rate, slots_pointer)`."""
    if len(data) != _INFO_SIZE:
        raise InvalidRomError(
            f"Gen III encounter header {map_index} {name} info has size "
            f"{len(data)}, expected {_INFO_SIZE}"
        )
    rate = data[0]
    slots_pointer = struct.unpack_from("<I", data, 4)[0]
    return rate, slots_pointer


def parse_method_slots(
    data: bytes, *, map_index: int, name: str, count: int
) -> tuple[WaterEncounterSlot, ...]:
    expected_size = count * _SLOT_SIZE
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III encounter header {map_index} {name} slots have size "
            f"{len(data)}, expected {expected_size}"
        )
    slots = []
    for index in range(count):
        min_level, max_level, species_id = struct.unpack_from(
            "<BBH", data, index * _SLOT_SIZE
        )
        slots.append(
            WaterEncounterSlot(
                minimum_level=min_level,
                maximum_level=max_level,
                species_id=species_id,
            )
        )
    return tuple(slots)


def parse_encounter_record(
    map_group: int,
    map_num: int,
    methods: dict[str, EncounterMethod | None],
    *,
    map_index: int,
    archive_path: str,
) -> MethodEncounterArea:
    """Assemble a fully-decoded `MethodEncounterArea` from a header's
    `map_group`/`map_num` (see `parse_header`) and each method's already
    fully-resolved `EncounterMethod` (rate + slots, see `parse_method_info`/
    `parse_method_slots`), or `None` for an absent method.
    """
    missing = set(methods) - set(ENCOUNTER_METHOD_NAMES)
    if missing:
        raise InvalidRomError(f"Unknown Gen III encounter method(s): {sorted(missing)}")
    return MethodEncounterArea(
        area_id=map_index,
        map_group=map_group,
        map_num=map_num,
        land=methods.get("land"),
        water=methods.get("water"),
        rock_smash=methods.get("rock_smash"),
        fishing=methods.get("fishing"),
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=map_index
        ),
    )
