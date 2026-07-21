from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import parse_map_events, parse_object_events
from romwiki.util.errors import InvalidRomError


class Gen4EventTests(unittest.TestCase):
    def test_decodes_object_event_and_validates_all_sections(self) -> None:
        object_data = struct.pack(
            "<6Hh3HhhHHi",
            4,
            6,
            15,
            1,
            0,
            3002,
            1,
            5,
            0,
            0,
            0,
            0,
            166,
            813,
            65536,
        )
        data = struct.pack("<I", 0) + struct.pack("<I", 1) + object_data
        data += struct.pack("<II", 0, 0)

        objects = parse_object_events(data, event_file_id=329)

        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0].script_id, 3002)
        self.assertEqual(objects[0].trainer_type, 1)
        self.assertEqual((objects[0].x, objects[0].z), (166, 813))

    def test_rejects_trailing_event_data(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_object_events(struct.pack("<IIII", 0, 0, 0, 0) + b"x", event_file_id=1)

    def test_decodes_warp_destination_and_position(self) -> None:
        warp = struct.pack("<6H", 4, 9, 27, 2, 0, 0)
        data = struct.pack("<III", 0, 0, 1) + warp + struct.pack("<I", 0)

        events = parse_map_events(data, event_file_id=12)

        self.assertEqual(events.objects, ())
        self.assertEqual(len(events.warps), 1)
        self.assertEqual((events.warps[0].x, events.warps[0].z), (4, 9))
        self.assertEqual(events.warps[0].destination_header_id, 27)
        self.assertEqual(events.warps[0].destination_warp_id, 2)

    def test_decodes_background_event(self) -> None:
        background = struct.pack("<HH4I", 8087, 2, 14, 9, 0, 4)
        data = struct.pack("<I", 1) + background + struct.pack("<III", 0, 0, 0)

        events = parse_map_events(data, event_file_id=44)

        self.assertEqual(len(events.backgrounds), 1)
        self.assertEqual(events.backgrounds[0].script_id, 8087)
        self.assertEqual(events.backgrounds[0].event_type, 2)
        self.assertEqual((events.backgrounds[0].x, events.backgrounds[0].z), (14, 9))


if __name__ == "__main__":
    unittest.main()
