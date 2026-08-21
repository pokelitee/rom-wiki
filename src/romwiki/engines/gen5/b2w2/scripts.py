"""Literal B2W2 trainer-battle commands decoded by the sequel leaf."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen5.b2w2.opcode_table import OPCODE_TABLE

# The win check is not the only command that can follow a battle. Of the 180
# retail B2W2 sites with valid trainer operands, only 59 are followed by
# `TrainerBattleIsVictory`; the rest continue with `VMCall`, `VMJump`,
# `WorkSetConst` and friends, and every one of those is a named command in this
# engine's own opcode table. Requiring the win check discarded two thirds of the
# scripted trainer battles. The follow-on is validated as a real command
# instead, matching `gen4/platinum/scripts.py` and the BW leaf.
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
    for offset in range(0, len(data) - 9):
        if data[offset : offset + 2] == single_signature:
            if struct.unpack_from("<H", data, offset + 8)[0] not in OPCODE_TABLE:
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
            if offset + 12 > len(data):
                continue
            if struct.unpack_from("<H", data, offset + 10)[0] not in OPCODE_TABLE:
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
