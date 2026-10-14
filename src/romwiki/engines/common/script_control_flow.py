"""Static control-flow walk shared by the Gen IV and Gen V field-script VMs.

Both VMs encode a command as a little-endian u16 opcode followed by
fixed-width operands (a 4-byte operand is a signed relative address), and
both resolve jump/call targets relative to the end of the instruction. Which
opcodes exist, their widths, and which of them jump, branch, or terminate are
each generation's own facts, supplied by that generation's disassembler.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

OpcodeTable = Mapping[int, tuple[str, tuple[int, ...]]]


@dataclass(frozen=True, slots=True)
class ScriptInstruction:
    offset: int
    opcode: int
    name: str
    params: tuple[int, ...]
    next_offset: int


@dataclass(frozen=True, slots=True)
class ScriptControlFlow:
    #: Unconditional jumps: only the target is reachable next.
    jumps: frozenset[int]
    #: Conditional jumps and calls: both the next instruction and the target
    #: are statically reachable.
    branches: frozenset[int]
    #: Commands after which the straight-line run ends.
    terminators: frozenset[int]


def disassemble_reachable(
    data: bytes,
    start: int,
    *,
    opcode_table: OpcodeTable,
    control_flow: ScriptControlFlow,
) -> dict[int, ScriptInstruction]:
    """Disassemble every statically-reachable instruction from `start`.

    Returns a dict keyed by instruction start offset. Unknown opcodes (not
    in `opcode_table`, or falling off the end of `data`) end that path
    without raising -- a dead end in one branch doesn't invalidate the
    instructions already found on other branches.
    """
    instructions: dict[int, ScriptInstruction] = {}
    worklist = [start]

    while worklist:
        cursor = worklist.pop()
        # Walk a straight-line run from `cursor`, stopping at a jump,
        # terminator, dead end, or code already decoded from another path.
        while 0 <= cursor < len(data) and cursor not in instructions:
            if cursor + 2 > len(data):
                break
            opcode = struct.unpack_from("<H", data, cursor)[0]
            entry = opcode_table.get(opcode)
            if entry is None:
                break
            name, widths = entry
            opstart = cursor
            cursor += 2
            params = []
            truncated = False
            for width in widths:
                if cursor + width > len(data):
                    truncated = True
                    break
                if width == 4:
                    value = struct.unpack_from("<i", data, cursor)[0]
                elif width == 2:
                    value = struct.unpack_from("<H", data, cursor)[0]
                else:
                    value = data[cursor]
                params.append(value)
                cursor += width
            if truncated:
                break

            instructions[opstart] = ScriptInstruction(
                offset=opstart,
                opcode=opcode,
                name=name,
                params=tuple(params),
                next_offset=cursor,
            )

            if opcode in control_flow.jumps:
                worklist.append(cursor + params[-1])
                break
            if opcode in control_flow.branches:
                worklist.append(cursor + params[-1])
                continue
            if opcode in control_flow.terminators:
                break

    return instructions
