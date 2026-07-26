from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

# `a/0/0/9`: one member per matrix, each a grid describing which real map
# headers are geographically adjacent (outdoor connections) -- the same
# underlying concept as Generation IV's own `layout.map_matrices`, just a
# different binary shape. Record layout adopted from
# FrostFalcon/FrostsGen5Editor's `MapMatrixNARC.cs` and verified against real
# Black ROM data: member 0's declared `width * height` cell count matches its
# own raw byte length exactly (29 * 27 cells, `type=1` so a header-ID grid
# follows the terrain-file grid), and decoding that grid places Route 1,
# Route 2, and Nuvema Town in real, contiguous, correctly-adjacent cells --
# see `gen5_bw/locations.py`'s `_MATRIX_ID_OFFSET` docstring for the
# cross-check that ties a map header to its matrix.
_HEADER_SIZE = 8
_TYPE_WITH_HEADER_GRID = 1


@dataclass(frozen=True, slots=True)
class Gen5MapMatrix:
    matrix_id: int
    width: int
    height: int
    header_ids: tuple[int, ...] | None


def parse_map_matrix(data: bytes, *, matrix_id: int) -> Gen5MapMatrix:
    if len(data) < _HEADER_SIZE:
        raise InvalidRomError(f"Gen V map matrix {matrix_id} is truncated")
    matrix_type = data[0]
    width, height = struct.unpack_from("<hh", data, 4)
    if width <= 0 or height <= 0:
        raise InvalidRomError(f"Gen V map matrix {matrix_id} has an invalid size")
    cell_count = width * height
    map_files_end = _HEADER_SIZE + cell_count * 4
    if map_files_end > len(data):
        raise InvalidRomError(f"Gen V map matrix {matrix_id} is truncated")

    header_ids = None
    if matrix_type == _TYPE_WITH_HEADER_GRID:
        header_ids_end = map_files_end + cell_count * 4
        if header_ids_end > len(data):
            raise InvalidRomError(
                f"Gen V map matrix {matrix_id} is missing its header-ID grid"
            )
        header_ids = tuple(
            value[0]
            for value in struct.iter_unpack("<i", data[map_files_end:header_ids_end])
        )

    return Gen5MapMatrix(
        matrix_id=matrix_id, width=width, height=height, header_ids=header_ids
    )
