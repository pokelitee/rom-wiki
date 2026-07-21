from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.util.errors import InvalidRomError


@dataclass(frozen=True, slots=True)
class Gen4MapMatrix:
    matrix_id: int
    width: int
    height: int
    name: str
    land_data_ids: tuple[int, ...]
    header_ids: tuple[int, ...] | None
    altitudes: tuple[int, ...] | None


def parse_map_matrix(data: bytes, *, matrix_id: int) -> Gen4MapMatrix:
    if len(data) < 5:
        raise InvalidRomError(f"Map matrix {matrix_id} is truncated")
    width, height, has_headers, has_altitudes, name_length = data[:5]
    cell_count = width * height
    name_end = 5 + name_length
    if width == 0 or height == 0 or name_end > len(data):
        raise InvalidRomError(f"Map matrix {matrix_id} has an invalid header")
    try:
        name = data[5:name_end].decode("ascii")
    except UnicodeDecodeError as error:
        raise InvalidRomError(f"Map matrix {matrix_id} name is not ASCII") from error

    position = name_end
    header_ids = None
    if has_headers:
        header_end = position + cell_count * 2
        if header_end > len(data):
            raise InvalidRomError(f"Map matrix {matrix_id} header grid is truncated")
        header_ids = tuple(
            value[0]
            for value in struct.iter_unpack("<H", data[position:header_end])
        )
        position = header_end

    altitudes = None
    if has_altitudes:
        end = position + cell_count
        if end > len(data):
            raise InvalidRomError(f"Map matrix {matrix_id} altitude grid is truncated")
        altitudes = tuple(data[position:end])
        position = end

    land_end = position + cell_count * 2
    if land_end > len(data):
        raise InvalidRomError(f"Map matrix {matrix_id} land-data grid is truncated")
    land_data_ids = tuple(
        value[0] for value in struct.iter_unpack("<H", data[position:land_end])
    )
    position = land_end
    if position != len(data):
        raise InvalidRomError(
            f"Map matrix {matrix_id} has {len(data) - position} trailing bytes"
        )
    return Gen4MapMatrix(
        matrix_id=matrix_id,
        width=width,
        height=height,
        name=name,
        land_data_ids=land_data_ids,
        header_ids=header_ids,
        altitudes=altitudes,
    )
