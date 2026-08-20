from __future__ import annotations

import struct
from collections.abc import Sequence

from romwiki.engines.gen4.script_disassembler import (
    Gen4Instruction,
    disassemble_function,
)
from romwiki.engines.gen4.script_opcode_table import OPCODE_TABLE
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
# Derived from the shared table (opcode + its own param widths) rather than
# hand-copied, so a correction there can't silently desync this offset math.
_CALL_WIDTH = 2 + sum(OPCODE_TABLE[_CALL_OPCODE][1])
_GET_STARTER_SPECIES = "GetPlayerStarterSpecies"
_GET_PLAYER_GENDER = "GetPlayerGender"
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
    bar `starter_branches.py` holds its own block resolution to.

    A subroutine may instead be gated by an outer `GetPlayerGender` check
    before either staged block (Platinum's Route 201 and Route 203 tag
    battles: the rival's own gender determines which nested starter-branch
    block runs, and the game's own name for that opposite-gender rival is
    what the resulting trainer records are named). That outer gate carries
    no starter information itself, so it is not folded into one family;
    instead each gender's block is independently confirmed against the
    exact staged-subroutine shape above and emitted as its own family, the
    same way a script staging multiple battle positions already gets one
    family per position. A subroutine gated by anything else is still
    deliberately not matched, rather than guessing at an unrecognized shape.

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
        if pairs is not None:
            family = _family_from_pairs(
                pairs, script_file_id=script_file_id, position=0
            )
            if family is not None:
                families.append(family)
            continue
        gender_targets = _parse_gender_gated_target(instructions, target)
        if gender_targets is None:
            continue
        position = 0
        for gender_target in gender_targets:
            gender_pairs = _parse_staged_subroutine(
                instructions,
                gender_target,
                dest_var=partner_var,
                trainer_count=trainer_count,
                starter_species=species_set,
            )
            if gender_pairs is None:
                continue
            family = _family_from_pairs(
                gender_pairs, script_file_id=script_file_id, position=position
            )
            if family is None:
                continue
            families.append(family)
            position += 1
    return tuple(families)


def _family_from_pairs(
    pairs: list[tuple[int | None, int]],
    *,
    script_file_id: int,
    position: int,
) -> Gen4StarterBranchFamily | None:
    fallthrough_species, fallthrough_id = pairs[-1]
    if fallthrough_species is not None or len(pairs) < 2:
        return None
    compared = pairs[:-1]
    if len({species for species, _ in compared}) != len(compared):
        return None
    return Gen4StarterBranchFamily(
        script_file_id=script_file_id,
        position=position,
        selected=tuple(compared),
        fallthrough_trainer_id=fallthrough_id,
    )


def _parse_gender_gated_target(
    instructions: dict[int, Gen4Instruction], start: int
) -> tuple[int, int] | None:
    """Recognize `GetPlayerGender` guarding two exclusive branch targets.

    Verified shape (Platinum's Route 201 and Route 203 tag battles):

        GetPlayerGender(G)
        CompareVarToValue(G, 0); GoToIf -> A
        CompareVarToValue(G, 1); GoToIf -> B

    Returns `(A, B)` -- which numeric gender code plays which role is not
    resolved further, since nothing downstream needs to distinguish them:
    each target is independently re-checked against the full staged-subroutine
    shape before either is trusted.
    """
    entry = instructions.get(start)
    if entry is None or entry.name != _GET_PLAYER_GENDER:
        return None
    gender_var = entry.params[0]
    compare_a = instructions.get(entry.next_offset)
    if (
        compare_a is None
        or compare_a.name != _COMPARE_VAR_TO_VALUE
        or compare_a.params != (gender_var, 0)
    ):
        return None
    goto_a = instructions.get(compare_a.next_offset)
    if goto_a is None or goto_a.name != _GOTO_IF or goto_a.params[0] != _GOTO_IF_TRUE:
        return None
    compare_b = instructions.get(goto_a.next_offset)
    if (
        compare_b is None
        or compare_b.name != _COMPARE_VAR_TO_VALUE
        or compare_b.params != (gender_var, 1)
    ):
        return None
    goto_b = instructions.get(compare_b.next_offset)
    if goto_b is None or goto_b.name != _GOTO_IF or goto_b.params[0] != _GOTO_IF_TRUE:
        return None
    target_a = goto_a.next_offset + goto_a.params[-1]
    target_b = goto_b.next_offset + goto_b.params[-1]
    return target_a, target_b


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
