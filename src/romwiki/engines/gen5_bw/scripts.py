from __future__ import annotations

import struct
from dataclasses import dataclass

# Gen V field-script opcodes needed to locate literal trainer-battle triggers.
# Adopted from FrostFalcon/FrostsGen5Editor's `bw1CommandList` (a community,
# actively-maintained BW1 script-command table) and independently cross-
# checked against real Black ROM bytes: walking a known static-encounter
# script (`black-us.toml`'s Magikarp fact, file 526 offset 0x758) from its own
# function-table start lands byte-exact on a `PokePartyAdd` call whose species
# parameter is 129 (Magikarp) at exactly that offset, confirming both this
# opcode's shape and the function-table header format below. `CallTrainerBattle`
# (0x85) is always immediately followed by `TrainerBattleIsVictory` (0x8D)
# reading the same result variable in every real occurrence found in the ROM
# (12/12 samples) -- the same "opcode signature + validating follow-on
# command" pattern this project's `gen4_dppt/scripts.py` already uses for
# Platinum's `StartTrainerBattle`/`CheckWonBattle`, so no full script
# disassembler is needed to find these.
FUNCTION_TABLE_END = 0xFD13
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
    """Find literal `CallTrainerBattle`/`CallTrainerMultiBattle` invocations.

    Battles whose trainer ID is supplied through a script variable (the
    generic sight-triggered-battle convention -- see
    `gen5_bw/overworld.py`) are intentionally not resolved here; only
    literal, in-script trainer IDs are returned, matching this project's
    "decode, don't guess" principle.
    """
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
            commands.append(Gen5TrainerBattleCommand(offset=offset, trainer_ids=trainer_ids))
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


def parse_function_table(data: bytes) -> tuple[int, ...]:
    """Read a Gen V script file's function-offset header table.

    Each member of the `Scripts` archive (`layout.scripts`) starts with a
    table of dword byte-offsets to its own script functions, terminated by an
    entry whose low 16 bits equal `FUNCTION_TABLE_END` (0xFD13). Verified
    against real Black ROM data across many script files (11/15/22/23-entry
    tables all agreeing exactly with the number of local script functions
    each map's NPCs reference -- see `gen5_bw/overworld.py`).
    """
    offsets = []
    pos = 0
    n = len(data)
    while pos + 4 <= n:
        value = struct.unpack_from("<I", data, pos)[0]
        if (value & 0xFFFF) == FUNCTION_TABLE_END:
            break
        offsets.append(value)
        pos += 4
    return tuple(offsets)
