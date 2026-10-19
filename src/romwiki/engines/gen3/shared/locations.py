from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence

from romwiki.schema import EncounterMapLocation, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import MAP_HEADER_SIZE

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
    subtable_data: bytes,
    *,
    gmapgroups_address: int,
) -> dict[tuple[int, int], int]:
    """Decode `gMapGroups`' second indirection level into a mapping from
    `(map_group, map_num)` to the ROM address of that map's `MapHeader`
    struct.

    `subtable_data` must be the raw bytes spanning from `group_pointers[0]`
    (the lowest address, verified ascending for both games) to
    `gmapgroups_address` -- every group's own pointer array is packed
    contiguously, in ascending group-index order, across exactly this span
    (verified against real ROM data: consecutive group-pointer differences,
    divided by 4, give each group's real map count, and every resulting
    map's region section resolves to a Town Map name on FireRed, LeafGreen,
    and Emerald).
    """
    bounds = (*group_pointers, gmapgroups_address)
    base = group_pointers[0]
    index: dict[tuple[int, int], int] = {}
    for group in range(len(group_pointers)):
        start, end = bounds[group], bounds[group + 1]
        if end < start or (end - start) % 4:
            raise InvalidRomError(
                f"Gen III map group {group} has an invalid boundary "
                f"(0x{start:x}-0x{end:x})"
            )
        for slot in range((end - start) // 4):
            offset = (start - base) + slot * 4
            (pointer,) = struct.unpack_from("<I", subtable_data, offset)
            index[(group, slot)] = pointer
    return index
