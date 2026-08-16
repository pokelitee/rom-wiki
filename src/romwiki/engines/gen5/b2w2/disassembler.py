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


__all__ = [
    "Gen5Instruction",
    "disassemble_function",
    "disassemble_script",
    "parse_function_offsets",
]
