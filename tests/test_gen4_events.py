from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import parse_object_events
from romwiki.errors import InvalidRomError


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


if __name__ == "__main__":
    unittest.main()
