from __future__ import annotations

from romwiki.engines.gen5.script_disassembler import (
    Gen5Instruction,
    parse_function_offsets,
)
from romwiki.engines.gen5.script_disassembler import (
    disassemble_function as _disassemble_function,
)

from .opcode_table import OPCODE_TABLE


def disassemble_function(data: bytes, start: int) -> dict[int, Gen5Instruction]:
    """Disassemble B2W2 bytecode reachable from one function-table entry."""
    return _disassemble_function(data, start, opcode_table=OPCODE_TABLE)


def find_calls(data: bytes, start: int, opcode: int) -> tuple[Gen5Instruction, ...]:
    instructions = disassemble_function(data, start)
    return tuple(
        instruction
        for instruction in sorted(instructions.values(), key=lambda value: value.offset)
        if instruction.opcode == opcode
    )


__all__ = [
    "Gen5Instruction",
    "disassemble_function",
    "find_calls",
    "parse_function_offsets",
]
