from __future__ import annotations

import struct
from collections.abc import Sequence

from romwiki.engines.gen4.script_disassembler import (
    Gen4Instruction,
    disassemble_function,
)
from romwiki.engines.gen4.script_table import (
    SCRIPT_COMMAND_COUNT,
    Gen4TrainerBattleCommand,
    parse_script_table,
)
from romwiki.engines.gen4.starter_branches import Gen4StarterBranchFamily

# Platinum's tag-battle command (partner, enemy1, enemy2), found and verified
# against real Platinum ROM data: it does not appear in `scrcmd.py`'s shared
# literal-battle scan at all (a different opcode, and its first operand is
# not always literal), so trainers only reachable through it were invisible
# to extraction. Only 5 sites exist in the whole game.
START_TAG_BATTLE = 0x02A0
_CALL_OPCODE = 0x1A
_CALL_WIDTH = 6  # opcode(2) + relative offset(4), per script_opcode_table.py
_GET_STARTER_SPECIES = "GetPlayerStarterSpecies"
_SET_VAR_FROM_VALUE = "SetVarFromValue"
_COMPARE_VAR_TO_VALUE = "CompareVarToValue"
_GOTO_IF = "GoToIf"
_RETURN = "Return"
_GOTO_IF_TRUE = 1


def parse_tag_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen4TrainerBattleCommand, ...]:
    """Find StartTagBattle sites' literal operands (partner, enemy1, enemy2).

    Tolerant of a non-literal (script-variable) slot: only operands that
    resolve to a real trainer ID are kept, rather than requiring every slot
    to be literal. Variable operands are >= 0x8000 and so are naturally
    excluded by the trainer-range check, the same way the shared
    two-operand scanner already tolerates an absent second trainer.

    Like the shared literal scanner, this assumes `data` is a real field
    script (called on `header.script_file_id`-linked files only); a
    malformed table raises rather than silently skipping.
    """
    code_offset = parse_script_table(data)
    signature = struct.pack("<H", START_TAG_BATTLE)
    commands = []
    for offset in range(code_offset, len(data) - 9):
        if data[offset : offset + 2] != signature:
            continue
        if struct.unpack_from("<H", data, offset + 8)[0] >= SCRIPT_COMMAND_COUNT:
            continue
        operands = struct.unpack_from("<HHH", data, offset + 2)
        trainer_ids: list[int] = []
        for value in operands:
            if 0 < value < trainer_count and value not in trainer_ids:
                trainer_ids.append(value)
        if trainer_ids:
            commands.append(
                Gen4TrainerBattleCommand(offset=offset, trainer_ids=tuple(trainer_ids))
            )
    return tuple(commands)


def parse_staged_partner_battle_families(
    data: bytes,
    *,
    script_file_id: int,
    trainer_count: int,
    starter_species: Sequence[int] | None,
) -> tuple[Gen4StarterBranchFamily, ...]:
    """Resolve StartTagBattle sites whose partner is staged by a called subroutine.

    Verified shape (found in Platinum's own recurring-rival tag battles,
    script members 201 and 236): the tag-battle site's partner operand is a
    script variable, set immediately beforehand by an unconditional `Call`
    to a subroutine of the exact form

        GetPlayerStarterSpecies(V)
        SetVarFromValue(P, id_1); CompareVarToValue(V, species_1); GoToIf
        SetVarFromValue(P, id_2); CompareVarToValue(V, species_2); GoToIf
        ...
        SetVarFromValue(P, id_N)   -- fallthrough, no compare needed
        Return

    `P` matching the tag-battle's own partner variable, and every compared
    species drawn from this profile's own decoded starter table, are what
    this requires before trusting a match -- the same "decode, don't guess"
    bar `starter_branches.py` holds its own block resolution to. A
    subroutine gated by anything else before `GetPlayerStarterSpecies` (for
    example, a player-gender check also seen in this game, which this
    schema has no condition kind to represent) is deliberately not matched,
    rather than silently dropping that extra condition.

    The two enemy operands are not resolved here: `parse_tag_battle_commands`
    already covers them as ordinary literal trainer references.
    """
    if not starter_species:
        return ()
    species_set = set(starter_species)
    try:
        code_offset = parse_script_table(data)
    except Exception:  # noqa: BLE001 - a script this decoder cannot walk is skipped
        return ()
    signature = struct.pack("<H", START_TAG_BATTLE)
    families = []
    for offset in range(code_offset, len(data) - 9):
        if data[offset : offset + 2] != signature:
            continue
        if struct.unpack_from("<H", data, offset + 8)[0] >= SCRIPT_COMMAND_COUNT:
            continue
        partner_var = struct.unpack_from("<H", data, offset + 2)[0]
        if partner_var < 0x8000:
            continue  # literal partner: nothing staged to resolve
        call = _find_call_immediately_before(data, offset)
        if call is None:
            continue
        _, target = call
        instructions = disassemble_function(data, target)
        pairs = _parse_staged_subroutine(
            instructions,
            target,
            dest_var=partner_var,
            trainer_count=trainer_count,
            starter_species=species_set,
        )
        if pairs is None:
            continue
        fallthrough_species, fallthrough_id = pairs[-1]
        if fallthrough_species is not None or len(pairs) < 2:
            continue
        compared = pairs[:-1]
        if len({species for species, _ in compared}) != len(compared):
            continue
        families.append(
            Gen4StarterBranchFamily(
                script_file_id=script_file_id,
                position=0,
                selected=tuple(compared),
                fallthrough_trainer_id=fallthrough_id,
            )
        )
    return tuple(families)


def _find_call_immediately_before(
    data: bytes, before_offset: int
) -> tuple[int, int] | None:
    call_offset = before_offset - _CALL_WIDTH
    if call_offset < 0:
        return None
    if struct.unpack_from("<H", data, call_offset)[0] != _CALL_OPCODE:
        return None
    relative = struct.unpack_from("<i", data, call_offset + 2)[0]
    target = call_offset + _CALL_WIDTH + relative
    if not 0 <= target < len(data):
        return None
    return call_offset, target


def _parse_staged_subroutine(
    instructions: dict[int, Gen4Instruction],
    start: int,
    *,
    dest_var: int,
    trainer_count: int,
    starter_species: set[int],
) -> list[tuple[int | None, int]] | None:
    """Walk the exact staged-battle shape from a `GetPlayerStarterSpecies` call.

    Returns `(species_id, trainer_id)` pairs in block order, with the final
    (fallthrough) entry's species as `None`. `None` overall if the shape
    doesn't match at every step -- this never guesses a partial result.
    """
    entry = instructions.get(start)
    if entry is None or entry.name != _GET_STARTER_SPECIES:
        return None
    starter_var = entry.params[0]
    offset = entry.next_offset
    pairs: list[tuple[int | None, int]] = []
    while True:
        set_instr = instructions.get(offset)
        if (
            set_instr is None
            or set_instr.name != _SET_VAR_FROM_VALUE
            or set_instr.params[0] != dest_var
        ):
            return None
        trainer_id = set_instr.params[1]
        if not 0 < trainer_id < trainer_count:
            return None
        next_instr = instructions.get(set_instr.next_offset)
        if next_instr is not None and next_instr.name == _RETURN:
            pairs.append((None, trainer_id))
            return pairs
        if (
            next_instr is None
            or next_instr.name != _COMPARE_VAR_TO_VALUE
            or next_instr.params[0] != starter_var
        ):
            return None
        species_id = next_instr.params[1]
        if species_id not in starter_species:
            return None
        goto = instructions.get(next_instr.next_offset)
        if goto is None or goto.name != _GOTO_IF or goto.params[0] != _GOTO_IF_TRUE:
            return None
        pairs.append((species_id, trainer_id))
        offset = goto.next_offset
