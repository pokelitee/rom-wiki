from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.shared.script_opcode_table import OPCODE_TABLE

# A real, control-flow-aware disassembler for Gen IV field-script bytecode,
# using `script_opcode_table.py`'s pret/pokeplatinum-derived table. Mirrors
# `gen5.script_disassembler`'s design: `GoTo` ends the current straight-line
# run (only its target is reachable next); `GoToIf`/`CallIf` continue the
# straight-line run *and* queue the branch/call target (both paths are
# statically reachable, since a static disassembler can't know which branch
# a given input takes); `Call` queues its target as reachable and also
# continues past itself (a call returns to its own next instruction). Jump
# and call targets are relative to the end of their own instruction, the
# same convention `script_table.py`'s own table parser and
# `starter_branches.py` already use (`relative_field + 4 + relative`).
_GOTO_OPCODE = 0x16
_GOTO_IF_OPCODE = 0x1C
_CALL_OPCODE = 0x1A
_CALL_IF_OPCODE = 0x1D
_END_OPCODE = 0x02
_RETURN_OPCODE = 0x1B
_RETURN_COMMON_SCRIPT_OPCODE = 0x15


@dataclass(frozen=True, slots=True)
class Gen4Instruction:
    offset: int
    opcode: int
    name: str
    params: tuple[int, ...]
    next_offset: int


def disassemble_function(
    data: bytes,
    start: int,
    *,
    opcode_table: dict[int, tuple[str, tuple[int, ...]]] = OPCODE_TABLE,
) -> dict[int, Gen4Instruction]:
    """Disassemble every statically-reachable instruction from `start`.

    Returns a dict keyed by instruction start offset. Unknown opcodes (not
    in `OPCODE_TABLE`, or falling off the end of `data`) end that path
    without raising -- a dead end in one branch doesn't invalidate the
    instructions already found on other branches.
    """
    instructions: dict[int, Gen4Instruction] = {}
    worklist = [start]

    while worklist:
        cursor = worklist.pop()
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

            instructions[opstart] = Gen4Instruction(
                offset=opstart,
                opcode=opcode,
                name=name,
                params=tuple(params),
                next_offset=cursor,
            )

            if opcode == _GOTO_OPCODE:
                worklist.append(cursor + params[-1])
                break
            if opcode in (_GOTO_IF_OPCODE, _CALL_OPCODE, _CALL_IF_OPCODE):
                worklist.append(cursor + params[-1])
                continue
            if opcode in (
                _END_OPCODE,
                _RETURN_OPCODE,
                _RETURN_COMMON_SCRIPT_OPCODE,
            ):
                break

    return instructions
