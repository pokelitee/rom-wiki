from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.errors import InvalidRomError


SCRIPT_TABLE_END = 0xFD13
START_TRAINER_BATTLE = 0x00E5
CHECK_WON_BATTLE = 0x00EC


@dataclass(frozen=True, slots=True)
class Gen4TrainerBattleCommand:
    offset: int
    trainer_ids: tuple[int, ...]


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen4TrainerBattleCommand, ...]:
    """Find literal trainer battles followed by Platinum's win check.

    The two-command sequence distinguishes actual battle invocations from values
    equal to the battle opcode inside operands or embedded script data. Battles
    whose trainer ID is supplied through a script variable are intentionally not
    resolved here.
    """
    code_offset = _parse_script_table(data)
    commands = []
    signature = struct.pack("<H", START_TRAINER_BATTLE)
    win_check = struct.pack("<H", CHECK_WON_BATTLE)

    for offset in range(code_offset, len(data) - 7):
        if data[offset : offset + 2] != signature:
            continue
        if data[offset + 6 : offset + 8] != win_check:
            continue
        first_trainer, second_trainer = struct.unpack_from("<HH", data, offset + 2)
        if not 0 < first_trainer < trainer_count:
            continue
        if second_trainer != 0 and not 0 < second_trainer < trainer_count:
            continue
        trainer_ids = (
            (first_trainer, second_trainer)
            if second_trainer
            else (first_trainer,)
        )
        commands.append(
            Gen4TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids)
        )
    return tuple(commands)


def _parse_script_table(data: bytes) -> int:
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
