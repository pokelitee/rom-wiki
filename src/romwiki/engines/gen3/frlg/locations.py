from __future__ import annotations

import struct

from romwiki.schema import EncounterMapLocation, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import GMAPGROUPS_GROUP_COUNT, MAP_HEADER_REGION_COUNT, MAP_HEADER_SIZE

# Generation III's map-header system (`gMapGroups`/`struct MapHeader` in the
# public pokefirered decompilation, `include/global.fieldmap.h`), verified
# against the real FireRed and LeafGreen ROMs.
#
# Unlike every other flat table this engine has decoded so far (personal,
# moves, items, trainers), map headers are NOT one contiguous table --
# `gMapGroups[group]` is a pointer to that group's own separate, contiguous
# array of full `MapHeader` structs. A full-ROM scan for this session's
# verified two games found three such contiguous segments, all resolving to
# real Sevii Islands/postgame locations (Berry Forest, Icefall Cave, Rocket
# Warehouse, Trainer Tower, the Tanoby chambers, Celadon Dept. Store, and
# more) -- see the profile TOML's `map_header_segments` parameter for the
# exact verified offsets. Kanto's own main-region map headers (Pallet Town
# through Cinnabar Island, Routes 1-25, and Kanto's dungeons) were not
# located within this session's verification effort; they use the same
# struct shape but live in ROM regions this scan didn't successfully
# isolate from unrelated binary data. This is a deliberately bounded first
# slice, not a claim that Kanto has no map headers -- widen
# `map_header_segments` once a real, verified Kanto segment is found.
#
# `MapHeader` (28 bytes, one per map):
#   0x00  mapLayout pointer (u32 GBA ROM address; not decoded this slice)
#   0x04  events pointer (u32 GBA ROM address, 0 if absent; not decoded)
#   0x08  mapScripts pointer (u32 GBA ROM address, 0 if absent; not decoded)
#   0x0C  connections pointer (u32 GBA ROM address, 0 if absent; not decoded)
#   0x10  music (u16 LE)
#   0x12  mapLayoutId (u16 LE)
#   0x14  regionMapSectionId (u8) -- index into the region-name table
#   0x15  cave (u8)
#   0x16  weather (u8)
#   0x17  mapType (u8)
#   0x18-0x1B  bikingAllowed/flags/floorNum/battleType (not decoded)
#
# The region-name table (`region_name_offset`/`region_name_count` in the
# profile TOML) is a *separate*, variable-length, back-to-back
# 0xFF-terminated string table -- decoded via
# `text.decode_gen3_text_sequence`, not the fixed-stride
# `decode_gen3_text_table` every other name table in this engine uses.
# Verified complete at exactly 109 entries for both games (index 0 =
# "PALLET TOWN" through index 108 = "CELADON DEPT."; the byte immediately
# after index 108's terminator is unambiguous non-text graphics data).


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
    region_names: list[str],
    *,
    count: int,
    archive_path: str,
) -> tuple[EncounterMapLocation, ...]:
    """Decode `count` concatenated 28-byte `MapHeader` records (already
    read and concatenated across every verified segment by the extraction
    layer, in segment order) into one `EncounterMapLocation` per header, a
    synthetic sequential `header_id` (0..count-1) identifying each.

    This slice decodes names only -- `matrix_id` has no real ROM-derived
    value yet (Generation III's outdoor-connection grid isn't decoded this
    pass) and is `0` for every record, not a guessed real fact. `warps`,
    `connections`, `items`, `trainers`, and every other optional field stay
    at their schema defaults.
    """
    if len(header_data) != count * MAP_HEADER_SIZE:
        raise InvalidRomError(
            f"Gen III map header table has size {len(header_data)}, "
            f"expected {count * MAP_HEADER_SIZE}"
        )
    if len(region_names) != MAP_HEADER_REGION_COUNT:
        raise InvalidRomError(
            f"Gen III region-name table has {len(region_names)} entries, "
            f"expected {MAP_HEADER_REGION_COUNT}"
        )
    records = []
    for header_id in range(count):
        raw = header_data[
            header_id * MAP_HEADER_SIZE : (header_id + 1) * MAP_HEADER_SIZE
        ]
        _music, _map_layout_id, region_id = parse_map_header(raw, header_id=header_id)
        if region_id >= len(region_names):
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


def parse_gmapgroups_pointers(data: bytes) -> tuple[int, ...]:
    """Decode `gMapGroups` itself: `GMAPGROUPS_GROUP_COUNT` consecutive GBA
    pointers, each the ROM address of that group's own array of
    pointers-to-`MapHeader` (see `constants.py`'s `GMAPGROUPS_GROUP_COUNT`
    comment for how this was verified).
    """
    expected_size = GMAPGROUPS_GROUP_COUNT * 4
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III gMapGroups table has size {len(data)}, expected {expected_size}"
        )
    return struct.unpack(f"<{GMAPGROUPS_GROUP_COUNT}I", data)


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
    divided by 4, give each group's real map count, cross-checked against
    every already-known Sevii Islands header's address).
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
