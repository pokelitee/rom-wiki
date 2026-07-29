from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import parse_map_matrix
from romwiki.util.errors import InvalidRomError


class Gen4MapMatrixTests(unittest.TestCase):
    def test_decodes_optional_altitude_and_header_grids(self) -> None:
        data = bytes((2, 1, 1, 1, 3)) + b"map"
        data += struct.pack("<2H", 7, 8)
        data += bytes((0, 4))
        data += struct.pack("<2H", 100, 101)

        matrix = parse_map_matrix(data, matrix_id=0)

        self.assertEqual((matrix.width, matrix.height), (2, 1))
        self.assertEqual(matrix.name, "map")
        self.assertEqual(matrix.altitudes, (0, 4))
        self.assertEqual(matrix.land_data_ids, (100, 101))
        self.assertEqual(matrix.header_ids, (7, 8))

    def test_rejects_trailing_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_matrix(bytes((1, 1, 0, 0, 0)) + b"\0\0x", matrix_id=1)


if __name__ == "__main__":
    unittest.main()
