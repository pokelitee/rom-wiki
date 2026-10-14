from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.overworld import parse_overworld_npcs


def _npc_record(
    *, script_used: int, sight_range: int, x: int, y: int, z: int, sprite: int = 0
) -> bytes:
    # 18 signed 16-bit fields, the same real-ROM layout as BW's own overworld
    # NPC records (see gen5/shared/overworld.py's module docstring): id, sprite,
    # movementPermissions, permissions2, flag, scriptUsed, defaultDirection,
    # sightRange, unknown1, unknown2, horizontalLeash, verticalLeash,
    # unknown3, unknown4, x, y, unknown5, z.
    return struct.pack(
        "<18h",
        0,
        sprite,
        0,
        0,
        0,
        script_used,
        0,
        sight_range,
        0,
        0,
        0,
        0,
        0,
        0,
        x,
        y,
        0,
        z,
    )


class B2W2OverworldNpcTests(unittest.TestCase):
    def test_parses_npc_records_after_the_furniture_section(self) -> None:
        furniture = struct.pack("<hhhihii", 0, 0, 0, 0, 0, 0, 0)  # 20 bytes, unused
        header = bytes((0, 0, 0, 0, 1, 2, 0, 0))  # 1 furniture, 2 NPCs
        npc0 = _npc_record(script_used=4, sight_range=0, x=12, y=3, z=1)
        npc1 = _npc_record(script_used=3009, sight_range=6, x=9, y=30, z=0)
        data = header + furniture + npc0 + npc1

        npcs = parse_overworld_npcs(data)

        self.assertEqual(len(npcs), 2)
        self.assertEqual(npcs[0].script_used, 4)
        self.assertEqual((npcs[0].x, npcs[0].y, npcs[0].z), (12, 3, 1))
        self.assertEqual(npcs[1].script_used, 3009)
        self.assertEqual(npcs[1].sight_range, 6)

    def test_empty_map_has_no_npcs(self) -> None:
        self.assertEqual(parse_overworld_npcs(b""), ())
        self.assertEqual(parse_overworld_npcs(bytes(8)), ())

    def test_stops_at_a_truncated_npc_record_instead_of_raising(self) -> None:
        header = bytes((0, 0, 0, 0, 0, 2, 0, 0))  # 0 furniture, header claims 2 NPCs
        npc0 = _npc_record(script_used=4, sight_range=0, x=12, y=3, z=1)
        data = header + npc0 + npc0[:10]  # second record cut short

        npcs = parse_overworld_npcs(data)

        self.assertEqual(len(npcs), 1)
        self.assertEqual(npcs[0].script_used, 4)


if __name__ == "__main__":
    unittest.main()
