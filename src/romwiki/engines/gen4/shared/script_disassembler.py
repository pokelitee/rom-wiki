from __future__ import annotations

from romwiki.engines.common.script_control_flow import (
    OpcodeTable,
    ScriptControlFlow,
    ScriptInstruction,
    disassemble_reachable,
)

# A real, control-flow-aware disassembler for Gen IV field-script bytecode.
# Each engine leaf supplies its own opcode table (`gen4/platinum/` and
# `gen4/hgss/script_opcode_table.py`): only the low-numbered VM control-flow
# opcodes below are shared, while the game-specific commands are numbered
# independently per family. Mirrors
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
_CONTROL_FLOW = ScriptControlFlow(
    jumps=frozenset({_GOTO_OPCODE}),
    branches=frozenset({_GOTO_IF_OPCODE, _CALL_OPCODE, _CALL_IF_OPCODE}),
    terminators=frozenset({_END_OPCODE, _RETURN_OPCODE, _RETURN_COMMON_SCRIPT_OPCODE}),
)

Gen4Instruction = ScriptInstruction


def disassemble_function(
    data: bytes,
    start: int,
    *,
    opcode_table: OpcodeTable,
) -> dict[int, Gen4Instruction]:
    """Disassemble every statically-reachable instruction from `start`.

    Returns a dict keyed by instruction start offset. Unknown opcodes (not
    in `opcode_table`, or falling off the end of `data`) end that path
    without raising -- a dead end in one branch doesn't invalidate the
    instructions already found on other branches.
    """
    return disassemble_reachable(
        data, start, opcode_table=opcode_table, control_flow=_CONTROL_FLOW
    )
