from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

MAP_HEADER_SIZE = 24
INTERNAL_MAP_NAME_SIZE = 16


@dataclass(frozen=True, slots=True)
class PlatinumMapHeader:
    header_id: int
    area_data_id: int
    unknown_value: int
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
                area_data_id=data[offset + 0x0],
                unknown_value=data[offset + 0x1],
                matrix_id=struct.unpack_from("<H", data, offset + 0x2)[0],
                script_file_id=struct.unpack_from("<H", data, offset + 0x4)[0],
                level_script_id=struct.unpack_from("<H", data, offset + 0x6)[0],
                text_archive_id=struct.unpack_from("<H", data, offset + 0x8)[0],
                day_music_id=struct.unpack_from("<H", data, offset + 0xA)[0],
                night_music_id=struct.unpack_from("<H", data, offset + 0xC)[0],
                encounter_id=struct.unpack_from("<H", data, offset + 0xE)[0],
                event_file_id=struct.unpack_from("<H", data, offset + 0x10)[0],
                location_name_id=data[offset + 0x12],
                map_label_window_id=data[offset + 0x13],
                weather_id=data[offset + 0x14],
                camera_id=data[offset + 0x15],
                # The last two bytes pack the map type, battle background,
                # and permission bits (bike/run/escape rope/fly). Kept as
                # the raw packed value until the bit layout is verified.
                flags=struct.unpack_from("<H", data, offset + 0x16)[0],
                internal_name=internal_name,
            )
        )
    return tuple(headers)
