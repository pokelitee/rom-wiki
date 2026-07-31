from __future__ import annotations

import struct

from romwiki.schema import EncounterMapLocation, RecordProvenance
from romwiki.util.errors import InvalidRomError

# `MapTableFile` (Ajarmar/universal-pokemon-randomizer-zx's Gen5RomHandler.java
# `loadWildMapNames`): one fixed 48-byte record per map header, member 0 of
# the archive.
MAP_HEADER_RECORD_SIZE = 48
_MATRIX_ID_OFFSET = 4
_SCRIPT_FILE_OFFSET = 6
_WILD_SET_OFFSET = 20
_NAME_INDEX_OFFSET = 26
_NULL_WILD_SET = 0xFFFF


def parse_map_header_script_files(data: bytes) -> tuple[int, ...]:
    if len(data) % MAP_HEADER_RECORD_SIZE:
        raise InvalidRomError("Gen V map header table has an invalid size")
    count = len(data) // MAP_HEADER_RECORD_SIZE
    return tuple(
        struct.unpack_from(
            "<H", data, header_id * MAP_HEADER_RECORD_SIZE + _SCRIPT_FILE_OFFSET
        )[0]
        for header_id in range(count)
    )


def parse_map_header_table(
    data: bytes,
    *,
    map_names: tuple[str, ...],
    archive_path: str,
    wild_set_mask: int,
) -> tuple[EncounterMapLocation, ...]:
    if len(data) % MAP_HEADER_RECORD_SIZE:
        raise InvalidRomError("Gen V map header table has an invalid size")
    count = len(data) // MAP_HEADER_RECORD_SIZE
    headers = []
    for header_id in range(count):
        base = header_id * MAP_HEADER_RECORD_SIZE
        wild_set = (
            struct.unpack_from("<H", data, base + _WILD_SET_OFFSET)[0] & wild_set_mask
        )
        name_index = data[base + _NAME_INDEX_OFFSET]
        matrix_id = struct.unpack_from("<H", data, base + _MATRIX_ID_OFFSET)[0]
        if name_index >= len(map_names):
            raise InvalidRomError(
                f"Gen V map header {header_id} references missing map name {name_index}"
            )
        headers.append(
            EncounterMapLocation(
                header_id=header_id,
                name=map_names[name_index],
                encounter_map_index=(
                    None if wild_set == (_NULL_WILD_SET & wild_set_mask) else wild_set
                ),
                matrix_id=matrix_id,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=header_id
                ),
            )
        )
    return tuple(headers)


def parse_wild_map_names(
    data: bytes, *, map_names: tuple[str, ...], wild_set_mask: int
) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for header in parse_map_header_table(
        data,
        map_names=map_names,
        archive_path="",
        wild_set_mask=wild_set_mask,
    ):
        if header.encounter_map_index is None:
            continue
        names = result.setdefault(header.encounter_map_index, [])
        if header.name not in names:
            names.append(header.name)
    return result
