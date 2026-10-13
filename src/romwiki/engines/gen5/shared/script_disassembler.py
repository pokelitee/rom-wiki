from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen5.shared.script_opcode_table import OPCODE_TABLE

# A real, control-flow-aware disassembler for Gen V field-script bytecode,
# using `script_opcode_table.py`'s adopted core table. Built after a
# straight-line-only walker (the technique that found trainer battles,
# warps, static encounters, and the fossil revival table) proved too
# unreliable for finding literal `CallFriendlyShopBuy` invocations: those
# scans produced hits whose own resolved shop ID didn't even name-match
# their real map (e.g. Castelia City's hit resolved to "Lacunosa
# Secondary"), meaning the byte pattern was landing inside unrelated data
# or another instruction's operands, not a real call.
#
# Two things this module gets right that the earlier scans didn't:
#
# 1. Jump/call target addressing. Empirically determined (not assumed):
#    sampling every `VMJump`/`VMJumpIf`/`VMCall`/`VMCallIf` instruction
#    found across many real script files and checking whether the
#    resolved target's own next two bytes decode as a valid opcode, using
#    "target = (position right after the full instruction) + signed
#    address operand" succeeds 526/527 times (99.8%) across a large real
#    sample -- versus 385/530 (72.6%) for "relative to the instruction's
#    own start". The near-100% hit rate is itself the verification: a
#    wrong addressing convention would not consistently land on valid
#    opcode bytes across hundreds of independent real jumps.
# 2. Real control flow, not just straight-line-to-halt. `VMJump` ends the
#    current straight-line run (unconditional -- only the jump target is
#    reachable next); `VMJumpIf`/`VMCallIf` continue the straight-line run
#    *and* queue the branch/call target (both paths are statically
#    reachable, since a static disassembler can't know which branch a
#    given input takes); `VMCall` queues its target as reachable and also
#    continues past itself (a call returns to its own next instruction).
#    A worklist of pending start offsets, deduplicated against what's
#    already been decoded, keeps this bounded and terminating.
_JUMP_OPCODE = 0x1E
_JUMP_IF_OPCODE = 0x1F
_CALL_OPCODE = 0x04
_CALL_IF_OPCODE = 0x20
_HALT_OPCODE = 0x02
_RETURN_OPCODE = 0x05
_FUNCTION_TABLE_END = 0xFD13


@dataclass(frozen=True, slots=True)
class Gen5Instruction:
    offset: int
    opcode: int
    name: str
    params: tuple[int, ...]
    next_offset: int


def parse_function_offsets(data: bytes) -> tuple[int, ...]:
    """Return the absolute starts in a Gen V script's function table."""
    offsets: list[int] = []
    cursor = 0
    while cursor + 2 <= len(data):
        if struct.unpack_from("<H", data, cursor)[0] == _FUNCTION_TABLE_END:
            return tuple(offsets)
        if cursor + 4 > len(data):
            break
        relative_offset = struct.unpack_from("<i", data, cursor)[0]
        target = cursor + 4 + relative_offset
        if not 0 <= target < len(data):
            return ()
        offsets.append(target)
        cursor += 4
    return ()


def disassemble_function(
    data: bytes,
    start: int,
    *,
    opcode_table: dict[int, tuple[str, tuple[int, ...]]] = OPCODE_TABLE,
) -> dict[int, Gen5Instruction]:
    """Disassemble every statically-reachable instruction from `start`.

    Returns a dict keyed by instruction start offset. Unknown opcodes (not
    in `OPCODE_TABLE`, or falling off the end of `data`) end that path
    without raising -- a dead end in one branch doesn't invalidate the
    instructions already found on other branches.
    """
    instructions: dict[int, Gen5Instruction] = {}
    worklist = [start]

    while worklist:
        cursor = worklist.pop()
        # Walk a straight-line run from `cursor`, stopping at a branch,
        # halt/return, dead end, or code already decoded from another path.
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

            instructions[opstart] = Gen5Instruction(
                offset=opstart,
                opcode=opcode,
                name=name,
                params=tuple(params),
                next_offset=cursor,
            )

            if opcode == _JUMP_OPCODE:
                worklist.append(cursor + params[-1])
                break
            if opcode in (_JUMP_IF_OPCODE, _CALL_OPCODE, _CALL_IF_OPCODE):
                worklist.append(cursor + params[-1])
                continue
            if opcode in (_HALT_OPCODE, _RETURN_OPCODE):
                break

    return instructions


def disassemble_script(
    data: bytes,
    *,
    opcode_table: dict[int, tuple[str, tuple[int, ...]]] = OPCODE_TABLE,
) -> tuple[Gen5Instruction, ...]:
    """Return every instruction reachable from a script's function table."""
    instructions = {
        offset: instruction
        for function_offset in parse_function_offsets(data)
        for offset, instruction in disassemble_function(
            data, function_offset, opcode_table=opcode_table
        ).items()
    }
    return tuple(sorted(instructions.values(), key=lambda value: value.offset))


def find_calls(data: bytes, start: int, opcode: int) -> tuple[Gen5Instruction, ...]:
    """Find every statically-reachable call to a specific opcode."""
    instructions = disassemble_function(data, start)
    return tuple(
        instruction
        for instruction in sorted(instructions.values(), key=lambda i: i.offset)
        if instruction.opcode == opcode
    )
