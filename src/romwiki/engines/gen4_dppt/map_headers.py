from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.errors import InvalidRomError


MAP_HEADER_SIZE = 24
INTERNAL_MAP_NAME_SIZE = 16


@dataclass(frozen=True, slots=True)
class PlatinumMapHeader:
    header_id: int
    matrix_id: int
    script_file_id: int
    level_script_id: int
    text_archive_id: int
    encounter_id: int
    event_file_id: int
    location_name_id: int
    internal_name: str


def parse_platinum_map_headers(
    data: bytes, internal_names: bytes, *, count: int
) -> tuple[PlatinumMapHeader, ...]:
    expected_header_size = count * MAP_HEADER_SIZE
    expected_name_size = count * INTERNAL_MAP_NAME_SIZE
    if len(data) != expected_header_size:
        raise InvalidRomError(
            f"Expected {expected_header_size} bytes of Platinum map headers, "
            f"got {len(data)}"
        )
    if len(internal_names) != expected_name_size:
        raise InvalidRomError(
            f"Expected {expected_name_size} bytes of internal map names, "
            f"got {len(internal_names)}"
        )

    headers = []
    for header_id in range(count):
        offset = header_id * MAP_HEADER_SIZE
        name_offset = header_id * INTERNAL_MAP_NAME_SIZE
        raw_name = internal_names[name_offset : name_offset + INTERNAL_MAP_NAME_SIZE]
        try:
            internal_name = raw_name.split(b"\0", 1)[0].decode("ascii")
        except UnicodeDecodeError as error:
            raise InvalidRomError(
                f"Internal map name {header_id} is not ASCII"
            ) from error
        headers.append(
            PlatinumMapHeader(
                header_id=header_id,
                matrix_id=struct.unpack_from("<H", data, offset + 0x2)[0],
                script_file_id=struct.unpack_from("<H", data, offset + 0x4)[0],
                level_script_id=struct.unpack_from("<H", data, offset + 0x6)[0],
                text_archive_id=struct.unpack_from("<H", data, offset + 0x8)[0],
                encounter_id=struct.unpack_from("<H", data, offset + 0xE)[0],
                event_file_id=struct.unpack_from("<H", data, offset + 0x10)[0],
                location_name_id=data[offset + 0x12],
                internal_name=internal_name,
            )
        )
    return tuple(headers)
