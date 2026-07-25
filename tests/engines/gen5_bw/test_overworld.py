from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.overworld import (
    parse_overworld_npcs,
    parse_overworld_warps,
    resolve_common_script_trainer_id,
)


def _npc_record(*, script_used: int, sight_range: int, x: int, y: int, z: int) -> bytes:
    # 18 signed 16-bit fields per real Black ROM record (see overworld.py's
    # module docstring): id, sprite, movementPermissions, permissions2, flag,
    # scriptUsed, defaultDirection, sightRange, unknown1, unknown2,
    # horizontalLeash, verticalLeash, unknown3, unknown4, x, y, unknown5, z.
    return struct.pack(
        "<18h", 0, 0, 0, 0, 0, script_used, 0, sight_range, 0, 0, 0, 0, 0, 0, x, y, 0, z
    )


class Gen5OverworldTests(unittest.TestCase):
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

    def test_resolves_real_banded_trainer_ids(self) -> None:
        # Real Black ROM facts: script member 155's NPCs include scriptUsed
        # 3026..3034 and 7040..7048, resolving to real, sequential, sensible
        # trainer records (26-34 and 40-48) when the band is subtracted.
        self.assertEqual(
            resolve_common_script_trainer_id(3026, trainer_count=616), 26
        )
        self.assertEqual(
            resolve_common_script_trainer_id(7048, trainer_count=616), 48
        )

    def test_does_not_resolve_local_script_indices(self) -> None:
        self.assertIsNone(resolve_common_script_trainer_id(4, trainer_count=616))
        self.assertIsNone(resolve_common_script_trainer_id(999, trainer_count=616))

    def test_does_not_resolve_out_of_range_bands(self) -> None:
        self.assertIsNone(resolve_common_script_trainer_id(2000, trainer_count=616))
        self.assertIsNone(resolve_common_script_trainer_id(9999, trainer_count=616))


def _warp_record(*, dest_header: int, dest_warp: int, x: int, y: int, z: int) -> bytes:
    return struct.pack("<hh", dest_header, dest_warp) + bytes(4) + struct.pack(
        "<hhh", x, y, z
    ) + bytes(6)


class Gen5OverworldWarpTests(unittest.TestCase):
    def test_parses_warp_records_after_npcs(self) -> None:
        # Real Black ROM shape: map 7 (Striaton City) has one warp into map 6
        # (destination warp 5), and map 6's own warp 5 reciprocates back to
        # map 7 -- confirmed by checking every warp in the ROM for this
        # reciprocity (858/873 real warps agree; the rest are genuine
        # one-way warps like holes and ledges).
        header = bytes((0, 0, 0, 0, 0, 0, 1, 0))  # 0 furniture, 0 NPCs, 1 warp
        warp = _warp_record(dest_header=6, dest_warp=5, x=184, y=0, z=696)
        data = header + warp

        warps = parse_overworld_warps(data)

        self.assertEqual(len(warps), 1)
        self.assertEqual(warps[0].destination_header_id, 6)
        self.assertEqual(warps[0].destination_warp_id, 5)
        self.assertEqual((warps[0].x, warps[0].y, warps[0].z), (184, 0, 696))

    def test_skips_past_furniture_and_npcs(self) -> None:
        header = bytes((0, 0, 0, 0, 1, 1, 1, 0))  # 1 furniture, 1 NPC, 1 warp
        furniture = bytes(20)
        npc = bytes(36)
        warp = _warp_record(dest_header=1, dest_warp=0, x=0, y=0, z=0)
        data = header + furniture + npc + warp

        warps = parse_overworld_warps(data)

        self.assertEqual(len(warps), 1)
        self.assertEqual(warps[0].destination_header_id, 1)

    def test_empty_map_has_no_warps(self) -> None:
        self.assertEqual(parse_overworld_warps(b""), ())
        self.assertEqual(parse_overworld_warps(bytes(8)), ())


if __name__ == "__main__":
    unittest.main()
