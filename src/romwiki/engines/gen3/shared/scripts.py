"""Static disassembler for Generation III event scripts.

A command is a one-byte opcode followed by fixed-width little-endian
operands; jump and call targets are absolute ROM addresses. The operand
widths are generated from pret/pokefirered's and pret/pokeemerald's
`asm/macros/event.inc` and `data/script_cmd_table.inc` into
`script_command_table.py` (see `scripts/pret/gen3_script_commands.py`). The
two games share opcodes 0x00-0xC6; each leaf adds its own later commands.

Disassembling every script reachable from every map's object, coordinate,
sign, and map-script events decodes about 25,000 FireRed/LeafGreen and
49,000 Emerald instructions with no unknown opcode and no jump outside the
ROM, which a single wrong width would break.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from romwiki.engines.common.script_control_flow import ScriptInstruction
from romwiki.util.errors import InvalidRomError

from .pointers import resolve_gba_pointer
from .script_command_table import COMMON_SCRIPT_COMMANDS as COMMON_SCRIPT_COMMANDS

ScriptCommandTable = Mapping[int, tuple[str, tuple[int, ...]]]

GOTO = 0x05
GOTO_IF = 0x06
CALL = 0x04
CALL_IF = 0x07
TRAINER_BATTLE = 0x5C
# `end`, `return`, `gotostd`, `returnram`/`endram`, `gotonative`, and the
# post-battle jumps end a straight-line run. So do warps (each leaf lists
# its own): a warp loads another map, so scripts often omit the `end` after
# one and the following bytes are data (an Emerald script ends `warp`,
# `waitstate`, then movement data).
_TERMINATORS = frozenset({0x02, 0x03, 0x08, 0x0C, 0x0D, 0x24, 0x5E, 0x5F})
COMMON_WARP_COMMANDS = frozenset({0x39, 0x3A, 0x3B, 0x3C, 0x3D})

# `trainerbattle type, trainer, local_id` is followed by a battle-type-
# dependent number of pointers; for some types the last is a script run
# after the battle. Types 9-12 differ by game and all take two text pointers.
_TRAINER_BATTLE_POINTERS = {0: 2, 1: 3, 2: 3, 3: 1, 4: 3, 5: 2, 6: 4, 7: 3, 8: 4}
_TRAINER_BATTLE_EXTRA_TYPES = range(9, 13)
_TRAINER_BATTLE_SCRIPT_TYPES = frozenset({1, 2, 6, 8})


def disassemble_script(
    read: Callable[[int, int], bytes],
    start: int,
    *,
    commands: ScriptCommandTable,
    warps: frozenset[int],
) -> dict[int, ScriptInstruction]:
    """Disassemble every instruction statically reachable from the script
    at ROM address `start`, keyed by ROM address.

    `read(offset, size)` returns ROM bytes and raises `InvalidRomError` past
    the end. An unknown opcode, an unreadable command, or a jump outside the
    ROM ends that path rather than raising: a hack can leave an object
    pointing at unused bytes (FireRed Omega has one).
    """
    instructions: dict[int, ScriptInstruction] = {}
    worklist = [start]
    while worklist:
        address = worklist.pop()
        while address not in instructions:
            instruction = _decode(read, address, commands)
            if instruction is None:
                break
            instructions[address] = instruction
            opcode, params = instruction.opcode, instruction.params
            if opcode in (GOTO, CALL):
                worklist.append(params[0])
            elif opcode in (GOTO_IF, CALL_IF):
                worklist.append(params[1])
            elif opcode == TRAINER_BATTLE and params[0] in _TRAINER_BATTLE_SCRIPT_TYPES:
                worklist.append(params[-1])
            if opcode == GOTO or opcode in _TERMINATORS or opcode in warps:
                break
            address = instruction.next_offset
    return instructions


def _decode(
    read: Callable[[int, int], bytes], address: int, commands: ScriptCommandTable
) -> ScriptInstruction | None:
    try:
        offset = resolve_gba_pointer(address)
        opcode = read(offset, 1)[0]
        entry = commands.get(opcode)
        if entry is None:
            return None
        name, widths = entry
        if opcode == TRAINER_BATTLE:
            kind = read(offset + 1, 1)[0]
            count = _TRAINER_BATTLE_POINTERS.get(kind)
            if count is None and kind in _TRAINER_BATTLE_EXTRA_TYPES:
                count = 2
            if count is None:
                return None
            widths = (*widths, *(4,) * count)
        data = read(offset + 1, sum(widths))
    except InvalidRomError:
        return None
    params, cursor = [], 0
    for width in widths:
        params.append(int.from_bytes(data[cursor : cursor + width], "little"))
        cursor += width
    return ScriptInstruction(
        offset=address,
        opcode=opcode,
        name=name,
        params=tuple(params),
        next_offset=address + 1 + cursor,
    )
