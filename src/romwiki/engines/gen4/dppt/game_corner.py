from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError


@dataclass(frozen=True, slots=True)
class Gen4GameCornerPrize:
    item_id: int
    price: int


def parse_game_corner_prizes(
    data: bytes, *, offset: int, count: int, item_count: int
) -> tuple[Gen4GameCornerPrize, ...]:
    prizes = []
    cursor = offset
    for _ in range(count):
        if cursor + 4 > len(data):
            raise InvalidRomError("Game Corner prize table is truncated")
        item_id, price = struct.unpack_from("<HH", data, cursor)
        cursor += 4
        if not 0 < item_id < item_count:
            raise InvalidRomError(
                f"Game Corner prize references invalid item {item_id}"
            )
        prizes.append(Gen4GameCornerPrize(item_id=item_id, price=price))
    return tuple(prizes)
