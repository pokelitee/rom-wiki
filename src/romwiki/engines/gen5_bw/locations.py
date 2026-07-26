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
# data: for several maps, walking that script member's own function-offset
# header table (dword offsets terminated by an entry whose low 16 bits equal
# 0xFD13) to the offset an NPC's `scriptUsed` field (1-indexed) selects lands
# on real, in-range script content -- see `gen5_bw/overworld.py`'s module
# docstring for the full cross-check. Offset 8 (the very next u16) is a
# second, related script member (consistently `script_file_offset + 1`)
# whose purpose isn't decoded.
_SCRIPT_FILE_OFFSET = 6


# Byte offset 4 (u16): the map's own matrix ID in `layout.map_matrices`
# (`a/0/0/9`) -- the map-grid mechanism outdoor connections use. Adopted from
# FrostFalcon/FrostsGen5Editor's `ZoneDataEntry`/`MapMatrixNARC.cs` and
# verified against real Black ROM data: header 317 (Route 1), 319 (Route 2),
# and 389 (Nuvema Town's outdoor plaza) all report matrix 0, and that
# matrix's own header-ID grid places all three in real, contiguous,
# correctly-adjacent cells (Nuvema Town directly south of Route 1, Route 1
# directly south of Route 2) -- matching the real game's geography exactly.
_MATRIX_ID_OFFSET = 4


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
        matrix_id = struct.unpack_from("<H", data, base + _MATRIX_ID_OFFSET)[0]
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
                matrix_id=matrix_id,
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
