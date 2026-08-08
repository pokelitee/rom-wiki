from __future__ import annotations

from romwiki.engines.gen5.script_disassembler import (
    Gen5Instruction,
    parse_function_offsets,
)
from romwiki.engines.gen5.script_disassembler import (
    disassemble_function as _disassemble_function,
)
from romwiki.engines.gen5.script_disassembler import (
    disassemble_script as _disassemble_script,
)

from .opcode_table import OPCODE_TABLE


def disassemble_function(data: bytes, start: int) -> dict[int, Gen5Instruction]:
    """Disassemble B2W2 bytecode reachable from one function-table entry."""
    return _disassemble_function(data, start, opcode_table=OPCODE_TABLE)


def disassemble_script(data: bytes) -> tuple[Gen5Instruction, ...]:
    """Disassemble every B2W2 function using the sequel opcode table."""
    return _disassemble_script(data, opcode_table=OPCODE_TABLE)


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
    "disassemble_script",
    "find_calls",
    "parse_function_offsets",
]
