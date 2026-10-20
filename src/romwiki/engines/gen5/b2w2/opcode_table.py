"""Black 2/White 2 field-script opcodes.

Generated from the pokebw2 decompilation, which rebuilds both ROMs byte for
byte from scripts reassembled with these command definitions (see
`script_command_table.py` and `scripts/generate/gen5_b2w2_script_commands.py`).
B2W2 renumbers and adds commands relative to Black/White, so it does not share
their table.
"""

from __future__ import annotations

from .script_command_table import SCRIPT_COMMANDS

#: Named here so `difficulty_branches.py`'s byte-pattern scan (which runs
#: before disassembly can resolve the opcode to its name) doesn't hand-copy
#: this table's own entry as a bare literal.
GAME_GET_DIFFICULTY = 0x2AF

OPCODE_TABLE = SCRIPT_COMMANDS
