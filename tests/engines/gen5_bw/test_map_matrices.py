from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.map_matrices import parse_map_matrix
from romwiki.util.errors import InvalidRomError


def _matrix(*, matrix_type: int, width: int, height: int, map_files, header_ids=None) -> bytes:
    data = bytes((matrix_type, 0, 0, 0)) + struct.pack("<hh", width, height)
    data += b"".join(struct.pack("<i", value) for value in map_files)
    if header_ids is not None:
        data += b"".join(struct.pack("<i", value) for value in header_ids)
    return data


class Gen5MapMatrixTests(unittest.TestCase):
    def test_decodes_a_header_grid_matrix(self) -> None:
        # Real Black ROM shape: matrix 0 is a 29x27 outdoor grid (type 1)
        # whose header-ID cells place Route 1, Route 2, and Nuvema Town in
        # real, contiguous, correctly-adjacent positions -- see
        # gen5_bw/locations.py's `_MATRIX_ID_OFFSET` docstring for the
        # cross-check. This is a small 2x2 analog of that same shape.
        data = _matrix(
            matrix_type=1,
            width=2,
            height=2,
            map_files=[100, 101, 102, 103],
            header_ids=[5, -1, 6, 7],
        )

        matrix = parse_map_matrix(data, matrix_id=0)

        self.assertEqual(matrix.width, 2)
        self.assertEqual(matrix.height, 2)
        self.assertEqual(matrix.header_ids, (5, -1, 6, 7))

    def test_type_zero_has_no_header_grid(self) -> None:
        data = _matrix(matrix_type=0, width=1, height=1, map_files=[108])

        matrix = parse_map_matrix(data, matrix_id=1)

        self.assertIsNone(matrix.header_ids)

    def test_rejects_truncated_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_matrix(b"\x01\x00\x00\x00\x02\x00\x02\x00", matrix_id=0)

    def test_rejects_zero_dimensions(self) -> None:
        data = bytes((0, 0, 0, 0)) + struct.pack("<hh", 0, 1)
        with self.assertRaises(InvalidRomError):
            parse_map_matrix(data, matrix_id=0)


if __name__ == "__main__":
    unittest.main()
