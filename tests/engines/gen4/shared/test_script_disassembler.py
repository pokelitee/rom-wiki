from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum.script_opcode_table import OPCODE_TABLE
from romwiki.engines.gen4.shared.script_disassembler import disassemble_function

_COMPARE_VAR_TO_VALUE = 0x0011
_GOTO_IF = 0x001C
_GOTO = 0x0016
_RETURN = 0x001B
_END = 0x0002


class Gen4ScriptDisassemblerTests(unittest.TestCase):
    def test_walks_a_straight_line_to_return(self) -> None:
        data = struct.pack("<HHH", _COMPARE_VAR_TO_VALUE, 0x800C, 5) + struct.pack(
            "<H", _RETURN
        )

        instructions = disassemble_function(data, 0, opcode_table=OPCODE_TABLE)

        self.assertEqual(len(instructions), 2)
        self.assertEqual(instructions[0].name, "CompareVarToValue")
        self.assertEqual(instructions[0].params, (0x800C, 5))
        self.assertEqual(instructions[6].name, "Return")

    def test_stops_at_end(self) -> None:
        data = struct.pack("<H", _END) + struct.pack("<H", _RETURN)

        instructions = disassemble_function(data, 0, opcode_table=OPCODE_TABLE)

        self.assertEqual(set(instructions), {0})

    def test_follows_an_unconditional_goto(self) -> None:
        # GoTo at 0 jumps past 4 bytes of padding to a Return at offset 10.
        goto = struct.pack("<H", _GOTO) + struct.pack("<i", 4)
        data = goto + b"\x00\x00\x00\x00" + struct.pack("<H", _RETURN)

        instructions = disassemble_function(data, 0, opcode_table=OPCODE_TABLE)

        self.assertEqual(set(instructions), {0, 10})
        self.assertEqual(instructions[10].name, "Return")

    def test_continues_past_a_conditional_goto_and_queues_its_target(self) -> None:
        # GoToIf at 0 (width 7) both falls through to offset 7 and queues a
        # target further out; both must be disassembled.
        goto_if = struct.pack("<HB", _GOTO_IF, 1) + struct.pack("<i", 3)
        data = (
            goto_if  # 0..6, next_offset=7, target = 7+3 = 10
            + struct.pack("<H", _RETURN)  # 7: fallthrough Return
            + b"\x00"
            + struct.pack("<H", _RETURN)  # 10: branch-target Return
        )

        instructions = disassemble_function(data, 0, opcode_table=OPCODE_TABLE)

        self.assertEqual(set(instructions), {0, 7, 10})

    def test_stops_on_an_unknown_opcode(self) -> None:
        data = struct.pack("<H", 0xFFFF)

        instructions = disassemble_function(data, 0, opcode_table=OPCODE_TABLE)

        self.assertEqual(instructions, {})


if __name__ == "__main__":
    unittest.main()
