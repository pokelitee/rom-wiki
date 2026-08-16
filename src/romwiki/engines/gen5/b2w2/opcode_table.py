"""B2W2 field-script opcodes needed for static-encounter discovery.

The base VM instruction shapes through 0x260 match the table used by BW and
were checked by walking all retail B2W2 static-encounter scripts from their
function tables. B2W2 changes the meanings of 0x174/0x177 and adds commands
above BW's table. The added widths below are independently fixed by real ROM
boundaries: each command lands exactly on the following known instruction in
the retail Black 2 and White 2 scripts. CheapScript's B2W2 command database and
the Project Pokémon B2W2 scripting research document the common VM, function
table, and relative control-flow format.
"""

from __future__ import annotations

from romwiki.engines.gen5.script_opcode_table import OPCODE_TABLE as BASE_OPCODE_TABLE

#: Named here so `difficulty_branches.py`'s byte-pattern scan (which runs
#: before disassembly can resolve the opcode to its name) doesn't hand-copy
#: this table's own entry as a bare literal.
GAME_GET_DIFFICULTY = 0x2AF

OPCODE_TABLE = {
    **BASE_OPCODE_TABLE,
    0x174: ("CallWildBattle", (2, 2, 2)),
    0x177: ("CallWildBattleEnd", ()),
    # Shiny/form-aware wild battle: species, level, form, result variable.
    0x297: ("CallWildBattleEx", (2, 2, 2, 2)),
    # Writes the current Easy/Normal/Challenge mode to a work variable; the
    # following stack comparison tests the result against mode value 2.
    0x2AF: ("GameGetDifficulty", (2,)),
    # Two actor-position commands in the Latias/Latios script.
    0x2BE: ("ActorMoveToGPosEx", (2, 2, 2, 2, 2, 2, 2)),
    # Special Zorua gift: destination, species, level, and three attributes.
    0x2EA: ("PokePartyAddN", (2, 2, 2, 2, 2, 2)),
}
