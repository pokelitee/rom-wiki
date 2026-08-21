from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.overworld import (
    decode_trainerbattle_id,
    parse_map_events,
    parse_object_event_template,
)
from romwiki.util.errors import InvalidRomError


def _map_events(
    *, object_event_count: int = 1, object_events_pointer: int = 0
) -> bytes:
    data = bytearray(20)
    data[0] = object_event_count
    struct.pack_into("<I", data, 0x04, object_events_pointer)
    return bytes(data)


def _object_event_template(
    *,
    local_id: int = 9,
    kind: int = 0,
    x: int = 17,
    y: int = 4,
    elevation: int = 3,
    trainer_type: int = 1,
    script_pointer: int = 0x081AB000,
) -> bytes:
    data = bytearray(24)
    data[0] = local_id
    data[2] = kind
    struct.pack_into("<hh", data, 0x04, x, y)
    data[0x08] = elevation
    struct.pack_into("<H", data, 0x0C, trainer_type)
    struct.pack_into("<I", data, 0x10, script_pointer)
    return bytes(data)


class ParseMapEventsTests(unittest.TestCase):
    def test_decodes_object_event_count_and_pointer(self) -> None:
        data = _map_events(object_event_count=5, object_events_pointer=0x081AC000)

        count, pointer = parse_map_events(data, header_id=0)

        self.assertEqual(count, 5)
        self.assertEqual(pointer, 0x081AC000)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_events(b"\x00" * 10, header_id=0)


class ParseObjectEventTemplateTests(unittest.TestCase):
    def test_decodes_normal_trainer_object(self) -> None:
        data = _object_event_template(
            local_id=9, kind=0, x=17, y=4, elevation=3, trainer_type=1
        )

        local_id, kind, x, y, elevation, trainer_type, script_pointer = (
            parse_object_event_template(data, header_id=14, index=8)
        )

        self.assertEqual(local_id, 9)
        self.assertEqual(kind, 0)
        self.assertEqual(x, 17)
        self.assertEqual(y, 4)
        self.assertEqual(elevation, 3)
        self.assertEqual(trainer_type, 1)
        self.assertEqual(script_pointer, 0x081AB000)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_object_event_template(b"\x00" * 10, header_id=0, index=0)


class DecodeTrainerbattleIdTests(unittest.TestCase):
    def test_decodes_trainer_id_from_trainerbattle_opcode(self) -> None:
        script = bytes([0x5C, 0x00]) + struct.pack("<H", 89)

        trainer_id = decode_trainerbattle_id(script)

        self.assertEqual(trainer_id, 89)

    def test_returns_none_for_a_non_trainerbattle_script(self) -> None:
        script = bytes([0x02, 0x00, 0x00, 0x00])

        self.assertIsNone(decode_trainerbattle_id(script))

    def test_returns_none_for_too_short_data(self) -> None:
        self.assertIsNone(decode_trainerbattle_id(b"\x5c\x00"))


if __name__ == "__main__":
    unittest.main()
