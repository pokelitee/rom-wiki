from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss import parse_map_headers
from romwiki.util.errors import InvalidRomError


class HGSSMapHeaderTests(unittest.TestCase):
    def test_decodes_packed_header_fields_and_internal_name(self) -> None:
        data = bytearray(24)
        data[0:2] = bytes((12, 3))
        struct.pack_into("<7H", data, 4, 9, 10, 11, 12, 13, 14, 15)
        struct.pack_into("<H", data, 18, 45 | (6 << 8))
        struct.pack_into("<I", data, 20, (7 << 1) | (21 << 12))

        header = parse_map_headers(bytes(data), b"ROUTE_01\0\0\0\0\0\0\0\0", count=1)[0]

        self.assertEqual(header.encounter_id, 12)
        self.assertEqual(header.matrix_id, 9)
        self.assertEqual(header.event_file_id, 15)
        self.assertEqual(header.location_name_id, 45)
        self.assertEqual(header.map_label_window_id, 6)
        self.assertEqual(header.weather_id, 7)
        self.assertEqual(header.camera_id, 21)
        self.assertEqual(header.internal_name, "ROUTE_01")

    def test_rejects_wrong_table_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_headers(bytes(23), bytes(16), count=1)


if __name__ == "__main__":
    unittest.main()
