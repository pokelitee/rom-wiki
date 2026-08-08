"""BW control-flow disassembler compatibility export."""

from romwiki.engines.gen5.script_disassembler import (
    Gen5Instruction,
    disassemble_function,
    disassemble_script,
    find_calls,
    parse_function_offsets,
)

__all__ = [
    "Gen5Instruction",
    "disassemble_function",
    "disassemble_script",
    "find_calls",
    "parse_function_offsets",
]
