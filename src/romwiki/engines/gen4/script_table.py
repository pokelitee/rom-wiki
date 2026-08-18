"""Generation IV's field-script table header, shared by both engine leaves.

Platinum and HeartGold/SoulSilver use the same layout: a run of signed
relative offsets, each measured from the end of its own field, ending either
at a terminator or at the first script it points to.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

SCRIPT_TABLE_END = 0xFD13

#: Upper bound (exclusive) on this generation's script opcode space, used by
#: both engine leaves to sanity-check a "does this look like a real
#: follow-on opcode" heuristic during byte-pattern script scanning.
SCRIPT_COMMAND_COUNT = 0x033A


@dataclass(frozen=True, slots=True)
class Gen4TrainerBattleCommand:
    offset: int
    trainer_ids: tuple[int, ...]


def parse_script_table(data: bytes) -> int:
    cursor = 0
    targets = []
    table_end = len(data)
    terminated = False
    while cursor < table_end:
        if cursor + 2 > len(data):
            raise InvalidRomError("Gen IV script table is truncated")
        if struct.unpack_from("<H", data, cursor)[0] == SCRIPT_TABLE_END:
            terminated = True
            break
        if cursor + 4 > table_end:
            raise InvalidRomError("Gen IV script table is truncated")
        relative_offset = struct.unpack_from("<i", data, cursor)[0]
        target = cursor + 4 + relative_offset
        targets.append(target)
        table_end = min(table_end, target)
        cursor += 4

    if not targets:
        raise InvalidRomError("Gen IV script table has no entries")
    if not terminated and cursor != table_end:
        raise InvalidRomError("Gen IV script table does not end at its first script")
    if any(target < table_end or target >= len(data) for target in targets):
        raise InvalidRomError("Gen IV script table contains an invalid entry offset")
    return table_end


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int, start_trainer_battle_opcode: int
) -> tuple[Gen4TrainerBattleCommand, ...]:
    """Find literal trainer battles whose operands and follow-on command validate.

    Shared scan algorithm for both engine leaves -- only the opcode differs
    per game (Platinum: 0x00E5; HeartGold/SoulSilver: 0x00D5, found and
    verified independently against real HGSS ROM data).

    A battle invocation is distinguished from values that merely equal the battle
    opcode inside operands or embedded script data by requiring valid trainer
    operands *and* a real script command immediately after the three-operand
    command -- the same "opcode signature plus validating follow-on command"
    shape `parse_roaming_activation_commands` uses.

    This deliberately does not require the follow-on to be `CheckWonBattle`.
    Requiring it silently dropped whole battle categories that handle their own
    result: on Platinum, the Elite Four's first and rematch battles are followed
    by `0x001B` and the rival battles by `0x0016`, so neither was resolved at
    all. Across every Platinum script file, every site with valid trainer
    operands is followed by a real command and names a trainer that has a
    party, while the neighbouring opcode values `0x00E4`, `0x00E6`, `0x00E7`,
    `0x0125`, and `0x0033` yield at most one such site between them -- the
    operand constraints, not the specific follow-on, are what carry the
    selectivity. Renegade Platinum shows the same shape with one additional
    follow-on command, which is why the command is validated generically
    rather than against a fixed list.

    Battles whose trainer ID is supplied through a script variable are still not
    resolved here: variable IDs are at or above 0x8000 and so fail the trainer
    range check.
    """
    code_offset = parse_script_table(data)
    commands = []
    signature = struct.pack("<H", start_trainer_battle_opcode)

    for offset in range(code_offset, len(data) - 7):
        if data[offset : offset + 2] != signature:
            continue
        if struct.unpack_from("<H", data, offset + 6)[0] >= SCRIPT_COMMAND_COUNT:
            continue
        first_trainer, second_trainer = struct.unpack_from("<HH", data, offset + 2)
        if not 0 < first_trainer < trainer_count:
            continue
        if second_trainer != 0 and not 0 < second_trainer < trainer_count:
            continue
        trainer_ids = (
            (first_trainer, second_trainer) if second_trainer else (first_trainer,)
        )
        commands.append(
            Gen4TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids)
        )
    return tuple(commands)
