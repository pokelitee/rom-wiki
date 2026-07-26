from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.disassembler import (
    disassemble_function,
    find_calls,
    parse_function_offsets,
)
from romwiki.engines.gen5_bw.marts import parse_shop_dispatch


def _vmnop() -> bytes:
    return struct.pack("<H", 0x0)


def _vmhalt() -> bytes:
    return struct.pack("<H", 0x2)


def _vmreturn() -> bytes:
    return struct.pack("<H", 0x5)


def _vmjump(addr: int) -> bytes:
    return struct.pack("<Hi", 0x1E, addr)


def _vmjump_if(cond: int, addr: int) -> bytes:
    return struct.pack("<H", 0x1F) + bytes((cond,)) + struct.pack("<i", addr)


def _vmcall(addr: int) -> bytes:
    return struct.pack("<Hi", 0x4, addr)


def _call_trainer_battle(tr1: int, tr2: int, flags: int) -> bytes:
    return struct.pack("<HHHH", 0x85, tr1, tr2, flags)


class Gen5DisassemblerTests(unittest.TestCase):
    def test_parses_function_table_and_shop_dispatch(self) -> None:
        function = (
            struct.pack("<HHH", 0x2A, 0x8000, 14)
            + struct.pack("<HHH", 0x2A, 0x8001, 0)
            + struct.pack("<HH", 0x1C, 10110)
            + _vmhalt()
        )
        data = struct.pack("<iH", 2, 0xFD13) + function

        offsets = parse_function_offsets(data)
        dispatch = parse_shop_dispatch(data, offsets[0])

        self.assertEqual(offsets, (6,))
        self.assertIsNotNone(dispatch)
        assert dispatch is not None
        self.assertEqual(dispatch.selector_id, 14)
        self.assertEqual(dispatch.mode, 0)
        self.assertEqual(dispatch.command_offset, 18)

    def test_decodes_a_straight_line_function(self) -> None:
        data = _vmnop() + _vmnop() + _vmhalt()

        instructions = disassemble_function(data, 0)

        self.assertEqual(
            [i.name for i in sorted(instructions.values(), key=lambda i: i.offset)],
            ["VMNop", "VMNop", "VMHalt"],
        )

    def test_unconditional_jump_skips_the_fallthrough(self) -> None:
        # `VMJump`'s target is real, reachable code; the bytes right after
        # the jump instruction are dead (e.g. embedded string/movement data)
        # and must NOT be decoded as if they were reachable.
        jump = _vmjump(2)  # target = end-of-instruction (6) + 2 = 8
        dead_bytes = b"\xff\xff"  # would misparse as a bogus opcode if reached
        target = _vmhalt()
        data = jump + dead_bytes + target

        instructions = disassemble_function(data, 0)

        self.assertIn(0, instructions)
        self.assertNotIn(6, instructions)
        self.assertIn(8, instructions)
        self.assertEqual(instructions[8].name, "VMHalt")

    def test_conditional_jump_reaches_both_branches(self) -> None:
        jump_if = _vmjump_if(255, 2)  # end-of-instruction (7) + 2 = 9
        fallthrough = _vmnop()
        target = _vmhalt()
        data = jump_if + fallthrough + target

        instructions = disassemble_function(data, 0)

        self.assertIn(0, instructions)
        self.assertIn(7, instructions)  # fallthrough VMNop
        self.assertIn(9, instructions)  # jump target VMHalt

    def test_call_reaches_target_and_returns_to_its_own_fallthrough(self) -> None:
        call = _vmcall(2)  # end-of-instruction (6) + 2 = 8
        after_call = _vmreturn()
        subroutine = _vmnop() + _vmreturn()
        data = call + after_call + subroutine

        instructions = disassemble_function(data, 0)

        self.assertIn(0, instructions)
        self.assertIn(6, instructions)  # the caller's own fallthrough
        self.assertIn(8, instructions)  # the called subroutine

    def test_finds_a_trainer_battle_reached_only_through_a_jump(self) -> None:
        # A linear-only walker (the technique used before this module
        # existed) would never see this instruction, since it only exists
        # past an unconditional jump.
        jump = _vmjump(2)
        dead_bytes = b"\x00\x00"
        battle = _call_trainer_battle(13, 0, 0)
        data = jump + dead_bytes + battle

        calls = find_calls(data, 0, 0x85)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].params, (13, 0, 0))

    def test_stops_cleanly_at_an_unknown_opcode(self) -> None:
        data = struct.pack("<H", 0xFFFF)

        instructions = disassemble_function(data, 0)

        self.assertEqual(instructions, {})

    def test_a_backward_jump_terminates_rather_than_looping(self) -> None:
        # `VMJump` back to the function's own start must not send the
        # disassembler into an infinite loop.
        data = _vmjump(-6)  # end-of-instruction (6) + (-6) = 0, i.e. itself

        instructions = disassemble_function(data, 0)

        self.assertEqual(list(instructions), [0])


if __name__ == "__main__":
    unittest.main()
