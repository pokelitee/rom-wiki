from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.disassembler import (
    disassemble_function,
    parse_function_offsets,
)


class B2W2DisassemblerTests(unittest.TestCase):
    def test_walks_b2w2_only_command_to_wild_battle(self) -> None:
        # The shape of Black 2's Latias/Latios script (member 304): a sequel-only
        # actor move, the wild battle, and its victory check.
        movement = struct.pack("<H5H", 0x2BE, 7, 48, 4, 12, 6)
        battle = struct.pack("<H3H", 0x174, 380, 68, 1)
        victory = struct.pack("<HH", 0x177, 0x8010)
        data = _script(movement + battle + victory + struct.pack("<H", 0x02))

        offsets = parse_function_offsets(data)
        instructions = disassemble_function(data, offsets[0])

        self.assertEqual(offsets, (6,))
        self.assertEqual(instructions[6].name, "ActorMoveLinear")
        self.assertEqual(instructions[18].name, "CallWildBattle")
        self.assertEqual(instructions[18].params, (380, 68, 1))
        self.assertEqual(instructions[26].name, "WildBattleIsVictory")
        self.assertEqual(instructions[30].name, "VMHalt")


def _script(code: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + code


if __name__ == "__main__":
    unittest.main()
