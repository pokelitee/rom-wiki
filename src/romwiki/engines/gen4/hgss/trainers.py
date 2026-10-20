from __future__ import annotations

import struct

from romwiki.engines.gen4.shared.trainers import TrainerClassPrizes
from romwiki.util.errors import InvalidRomError

# `sPrizeMoneyTbl` (pret/pokeheartgold `src/battle/battle_command.c`): 0x81
# rows of (u16 trainer class, u16 multiplier). The battle code finds a class's
# first row and falls back to row 2 for a class the table doesn't list.
PRIZE_TABLE_ROWS = 0x81
_PRIZE_ROW = struct.Struct("<HH")
_PRIZE_FALLBACK_ROW = 2


def parse_trainer_class_prize_multipliers(
    data: bytes, *, count: int
) -> TrainerClassPrizes:
    """Decode HeartGold/SoulSilver's prize table into per-class multipliers.

    `data` starts at the table; `count` is the number of trainer classes.
    """
    size = PRIZE_TABLE_ROWS * _PRIZE_ROW.size
    if len(data) < size:
        raise InvalidRomError(
            f"HGSS trainer prize table has size {len(data)}; expected {size}"
        )
    rows = [
        _PRIZE_ROW.unpack_from(data, index * _PRIZE_ROW.size)
        for index in range(PRIZE_TABLE_ROWS)
    ]
    first_row: dict[int, int] = {}
    for index, (class_id, _) in enumerate(rows):
        first_row.setdefault(class_id, index)
    chosen = [first_row.get(class_id, _PRIZE_FALLBACK_ROW) for class_id in range(count)]
    return TrainerClassPrizes(
        multipliers=tuple(rows[row][1] for row in chosen),
        # The multiplier is the second half-word of its row.
        offsets=tuple(row * _PRIZE_ROW.size + 2 for row in chosen),
    )
