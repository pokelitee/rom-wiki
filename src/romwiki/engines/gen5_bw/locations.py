from __future__ import annotations

import struct

from romwiki.schema import Gen5Location, RecordProvenance
from romwiki.util.errors import InvalidRomError

# `MapTableFile` (Ajarmar/universal-pokemon-randomizer-zx's Gen5RomHandler.java
# `loadWildMapNames`): one fixed 48-byte record per map header, member 0 of
# the archive. Only two fields are decoded here -- the display-name index and
# the wild-encounter-table index ("wild set") -- since that's all this
# generation's own randomizer code uses map headers for, and no public
# reference documents the rest of the record (warps, connections, scripts,
# music, ...); guessing at undocumented byte offsets without a way to verify
# them isn't done here, tracked as the bigger, still-open Locations gap.
MAP_HEADER_RECORD_SIZE = 48
_NAME_INDEX_OFFSET = 26
_WILD_SET_OFFSET = 20
_NULL_WILD_SET = 0xFFFF
# Byte offset 6 (u16): the map's own dedicated member index in `layout.scripts`
# (`a/0/5/7`) -- undecoded until this session. Verified against real Black ROM
# data: for several maps, walking the function this field's script member
# points to (via `gen5_bw/scripts.py`'s function table) at the offset an NPC's
# `scriptUsed` field (1-indexed) selects lands on real, in-range script
# content -- see `gen5_bw/overworld.py`'s module docstring for the full
# cross-check. Offset 8 (the very next u16) is a second, related script
# member (consistently `script_file_offset + 1`) whose purpose isn't decoded.
_SCRIPT_FILE_OFFSET = 6


def parse_map_header_script_files(data: bytes) -> tuple[int, ...]:
    if len(data) % MAP_HEADER_RECORD_SIZE:
        raise InvalidRomError("Gen V map header table has an invalid size")
    count = len(data) // MAP_HEADER_RECORD_SIZE
    return tuple(
        struct.unpack_from("<H", data, header_id * MAP_HEADER_RECORD_SIZE + _SCRIPT_FILE_OFFSET)[0]
        for header_id in range(count)
    )


def parse_map_header_table(
    data: bytes, *, map_names: tuple[str, ...], archive_path: str
) -> tuple[Gen5Location, ...]:
    if len(data) % MAP_HEADER_RECORD_SIZE:
        raise InvalidRomError("Gen V map header table has an invalid size")
    count = len(data) // MAP_HEADER_RECORD_SIZE
    headers = []
    for header_id in range(count):
        base = header_id * MAP_HEADER_RECORD_SIZE
        wild_set = struct.unpack_from("<H", data, base + _WILD_SET_OFFSET)[0]
        name_index = data[base + _NAME_INDEX_OFFSET]
        if name_index >= len(map_names):
            raise InvalidRomError(
                f"Gen V map header {header_id} references missing map name "
                f"{name_index}"
            )
        headers.append(
            Gen5Location(
                header_id=header_id,
                name=map_names[name_index],
                encounter_map_index=(
                    None if wild_set == _NULL_WILD_SET else wild_set
                ),
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=header_id
                ),
            )
        )
    return tuple(headers)


def parse_wild_map_names(
    data: bytes, *, map_names: tuple[str, ...]
) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for header in parse_map_header_table(data, map_names=map_names, archive_path=""):
        if header.encounter_map_index is None:
            continue
        names = result.setdefault(header.encounter_map_index, [])
        if header.name not in names:
            names.append(header.name)
    return result
