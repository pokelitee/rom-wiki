from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

MAP_HEADER_SIZE = 24
INTERNAL_MAP_NAME_SIZE = 16


@dataclass(frozen=True, slots=True)
class HGSSMapHeader:
    header_id: int
    area_data_id: int
    matrix_id: int
    script_file_id: int
    level_script_id: int
    text_archive_id: int
    day_music_id: int
    night_music_id: int
    encounter_id: int
    event_file_id: int
    location_name_id: int
    map_label_window_id: int
    weather_id: int
    camera_id: int
    flags: int
    internal_name: str


def parse_map_headers(
    data: bytes, internal_names: bytes, *, count: int
) -> tuple[HGSSMapHeader, ...]:
    if len(data) != count * MAP_HEADER_SIZE:
        raise InvalidRomError(
            f"Expected {count * MAP_HEADER_SIZE} bytes of HGSS map headers, "
            f"got {len(data)}"
        )
    if len(internal_names) != count * INTERNAL_MAP_NAME_SIZE:
        raise InvalidRomError(
            f"Expected {count * INTERNAL_MAP_NAME_SIZE} bytes of HGSS map names, "
            f"got {len(internal_names)}"
        )
    headers = []
    for header_id in range(count):
        offset = header_id * MAP_HEADER_SIZE
        raw_name = internal_names[
            header_id * INTERNAL_MAP_NAME_SIZE : (header_id + 1)
            * INTERNAL_MAP_NAME_SIZE
        ]
        try:
            internal_name = raw_name.split(b"\0", 1)[0].decode("ascii")
        except UnicodeDecodeError as error:
            raise InvalidRomError(
                f"Internal HGSS map name {header_id} is not ASCII"
            ) from error
        packed_location = struct.unpack_from("<H", data, offset + 18)[0]
        packed_flags = struct.unpack_from("<I", data, offset + 20)[0]
        encounter_id = data[offset]
        headers.append(
            HGSSMapHeader(
                header_id=header_id,
                area_data_id=data[offset + 1],
                matrix_id=struct.unpack_from("<H", data, offset + 4)[0],
                script_file_id=struct.unpack_from("<H", data, offset + 6)[0],
                level_script_id=struct.unpack_from("<H", data, offset + 8)[0],
                text_archive_id=struct.unpack_from("<H", data, offset + 10)[0],
                day_music_id=struct.unpack_from("<H", data, offset + 12)[0],
                night_music_id=struct.unpack_from("<H", data, offset + 14)[0],
                encounter_id=encounter_id,
                event_file_id=struct.unpack_from("<H", data, offset + 16)[0],
                location_name_id=packed_location & 0xFF,
                map_label_window_id=(packed_location >> 8) & 0xF,
                weather_id=(packed_flags >> 1) & 0x7F,
                camera_id=(packed_flags >> 12) & 0x3F,
                flags=packed_flags,
                internal_name=internal_name,
            )
        )
    return tuple(headers)
