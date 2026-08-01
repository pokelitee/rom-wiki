from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.disassembler import (
    disassemble_function,
    parse_function_offsets,
)


class B2W2DisassemblerTests(unittest.TestCase):
    def test_walks_b2w2_only_command_to_wild_battle(self) -> None:
        movement = struct.pack("<H7H", 0x2BE, 7, 50, 4, 12, 18, 3, 32)
        battle = struct.pack("<H3H", 0x174, 380, 68, 1)
        data = _script(movement + battle + struct.pack("<H", 0x177))

        offsets = parse_function_offsets(data)
        instructions = disassemble_function(data, offsets[0])

        self.assertEqual(offsets, (6,))
        self.assertEqual(instructions[6].name, "ActorMoveToGPosEx")
        self.assertEqual(instructions[22].name, "CallWildBattle")
        self.assertEqual(instructions[22].params, (380, 68, 1))
        self.assertEqual(instructions[30].name, "CallWildBattleEnd")


def _script(code: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + code


if __name__ == "__main__":
    unittest.main()
