"""Literal B2W2 trainer-battle commands decoded by the sequel leaf."""

from __future__ import annotations

import struct
from dataclasses import dataclass

START_TRAINER_BATTLE = 0x0085
START_TRAINER_MULTI_BATTLE = 0x0086
CHECK_TRAINER_BATTLE_WON = 0x008D


@dataclass(frozen=True, slots=True)
class Gen5TrainerBattleCommand:
    offset: int
    trainer_ids: tuple[int, ...]


def parse_trainer_battle_commands(
    data: bytes, *, trainer_count: int
) -> tuple[Gen5TrainerBattleCommand, ...]:
    commands = []
    single_signature = struct.pack("<H", START_TRAINER_BATTLE)
    multi_signature = struct.pack("<H", START_TRAINER_MULTI_BATTLE)
    win_check = struct.pack("<H", CHECK_TRAINER_BATTLE_WON)
    for offset in range(0, len(data) - 9):
        if data[offset : offset + 2] == single_signature:
            if data[offset + 8 : offset + 10] != win_check:
                continue
            first_trainer, second_trainer, _flags = struct.unpack_from(
                "<HHH", data, offset + 2
            )
            if not 0 < first_trainer < trainer_count:
                continue
            if second_trainer != 0 and not 0 < second_trainer < trainer_count:
                continue
            trainer_ids = (
                (first_trainer, second_trainer) if second_trainer else (first_trainer,)
            )
            commands.append(
                Gen5TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids)
            )
        elif data[offset : offset + 2] == multi_signature:
            if offset + 12 > len(data) or data[offset + 10 : offset + 12] != win_check:
                continue
            ally, first_trainer, second_trainer, _flags = struct.unpack_from(
                "<HHHH", data, offset + 2
            )
            if not (
                0 < ally < trainer_count
                and 0 < first_trainer < trainer_count
                and 0 < second_trainer < trainer_count
            ):
                continue
            commands.append(
                Gen5TrainerBattleCommand(
                    offset=offset, trainer_ids=(ally, first_trainer, second_trainer)
                )
            )
    return tuple(commands)
