from __future__ import annotations

import struct
from collections.abc import Callable, Mapping, Sequence

from romwiki.schema import EncounterMapLocation, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import (
    MAP_HEADER_SIZE,
    MAP_LAYOUT_PREFIX_SIZE,
    MAX_MAP_DIMENSION,
    MAX_MAPS_PER_GROUP,
)
from .pointers import resolve_gba_pointer

# `struct MapHeader` (28 bytes), verified against both FireRed/LeafGreen and
# Emerald: four leading pointers (mapLayout/events/mapScripts/connections,
# not decoded here), music/mapLayoutId (u16 each), regionMapSectionId (u8,
# the map's Town Map section), cave/weather/mapType/flag bytes (not
# decoded). Map headers aren't one flat table: `gMapGroups[group][num]`
# points to each map's header, so every map is reached through it (see
# `pipeline/extraction/map_headers.py`'s `iter_gba_map_headers`). Each
# section's name comes from a separate per-game pointer table; see each
# leaf's `REGION_NAME_*` constants.


def parse_map_header(data: bytes, *, header_id: int) -> tuple[int, int, int]:
    """Decode a 28-byte `MapHeader` into `(music, map_layout_id,
    region_map_section_id)`. The four leading pointer fields and the
    cave/weather/map_type/flag bytes aren't needed for this slice (no map
    layout, events, scripts, or connections are decoded) and are ignored.
    """
    if len(data) != MAP_HEADER_SIZE:
        raise InvalidRomError(
            f"Gen III map header {header_id} has size {len(data)}, "
            f"expected {MAP_HEADER_SIZE}"
        )
    music, map_layout_id = struct.unpack_from("<HH", data, 0x10)
    region_map_section_id = data[0x14]
    return music, map_layout_id, region_map_section_id


def parse_map_header_table(
    header_data: bytes,
    region_names: Mapping[int, str],
    *,
    header_ids: Sequence[int],
    archive_path: str,
) -> tuple[EncounterMapLocation, ...]:
    """Decode concatenated 28-byte `MapHeader` records into one
    `EncounterMapLocation` each, identified by the matching synthetic
    `header_ids` entry (see `iter_gba_map_headers`). `region_names` maps
    each region map section to its name.

    This slice decodes names only -- `matrix_id` has no real ROM-derived
    value yet (Generation III's outdoor-connection grid isn't decoded this
    pass) and is `0` for every record, not a guessed real fact. `warps`,
    `connections`, `items`, `trainers`, and every other optional field stay
    at their schema defaults.
    """
    expected_size = len(header_ids) * MAP_HEADER_SIZE
    if len(header_data) != expected_size:
        raise InvalidRomError(
            f"Gen III map header table has size {len(header_data)}, "
            f"expected {expected_size}"
        )
    records = []
    for index, header_id in enumerate(header_ids):
        raw = header_data[index * MAP_HEADER_SIZE : (index + 1) * MAP_HEADER_SIZE]
        _music, _map_layout_id, region_id = parse_map_header(raw, header_id=header_id)
        if region_id not in region_names:
            raise InvalidRomError(
                f"Gen III map header {header_id} references unknown region {region_id}"
            )
        records.append(
            EncounterMapLocation(
                header_id=header_id,
                name=region_names[region_id],
                encounter_map_index=None,
                matrix_id=0,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=header_id
                ),
            )
        )
    return tuple(records)


def parse_gmapgroups_pointers(data: bytes, *, group_count: int) -> tuple[int, ...]:
    """Decode `gMapGroups` itself: `group_count` consecutive GBA pointers,
    each the ROM address of that group's own array of pointers-to-
    `MapHeader` (see each leaf's own `GMAPGROUPS_GROUP_COUNT` comment for
    how this was verified).
    """
    expected_size = group_count * 4
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III gMapGroups table has size {len(data)}, expected {expected_size}"
        )
    return struct.unpack(f"<{group_count}I", data)


def parse_map_group_index(
    group_pointers: tuple[int, ...],
    read: Callable[[int, int], bytes],
    *,
    gmapgroups_address: int,
) -> dict[tuple[int, int], int]:
    """Decode `gMapGroups`' second indirection level into a mapping from
    `(map_group, map_num)` to the ROM address of that map's `MapHeader`.

    `read(offset, size)` returns ROM bytes. The ROM stores no per-group map
    count. Retail games pack every group's pointer array contiguously in
    group order, ending at `gMapGroups`, so the next array (or `gMapGroups`)
    bounds each group; this gives FireRed/LeafGreen's 425 and Emerald's 518
    maps. Hacks can move `gMapGroups` and add groups elsewhere (FireRed
    Omega appends a 44th), which leaves no array above the last ones, so a
    group also ends at its first entry that doesn't point to a map header.
    """
    bounds = sorted({*group_pointers, gmapgroups_address})
    index: dict[tuple[int, int], int] = {}
    for group, start in enumerate(group_pointers):
        end = next((bound for bound in bounds if bound > start), None)
        slots = MAX_MAPS_PER_GROUP if end is None else (end - start) // 4
        for num in range(min(slots, MAX_MAPS_PER_GROUP)):
            entry = read(resolve_gba_pointer(start) + num * 4, 4)
            (address,) = struct.unpack("<I", entry)
            if not _is_map_header(address, read):
                break
            index[(group, num)] = address
        if (group, 0) not in index:
            raise InvalidRomError(f"Gen III map group {group} has no map headers")
    return index


def _is_map_header(address: int, read: Callable[[int, int], bytes]) -> bool:
    try:
        header = read(resolve_gba_pointer(address), MAP_HEADER_SIZE)
        (layout_address,) = struct.unpack_from("<I", header, 0)
        layout = read(resolve_gba_pointer(layout_address), MAP_LAYOUT_PREFIX_SIZE)
    except InvalidRomError:
        return False
    width, height, *pointers = struct.unpack("<2i4I", layout)
    return (
        0 < width <= MAX_MAP_DIMENSION
        and 0 < height <= MAX_MAP_DIMENSION
        and all(_is_rom_pointer(pointer) for pointer in pointers)
    )


def _is_rom_pointer(value: int) -> bool:
    try:
        resolve_gba_pointer(value)
    except InvalidRomError:
        return False
    return True
