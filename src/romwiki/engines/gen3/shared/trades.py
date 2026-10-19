"""Generation III in-game trades (`struct InGameTrade`).

pret/pokefirered's `src/trade_scene.c` and pret/pokeemerald's
`src/trade.c` give the layout, and both games' tables use the same
60-byte rows: an 11-byte nickname, u16 species at 0x0C, six IVs at 0x0E,
the ability slot at 0x14, u32 OT ID at 0x18, five contest conditions at
0x1C, u32 personality at 0x24, u16 held item at 0x28, the mail index at
0x2A, an 11-byte OT name at 0x2B, OT gender at 0x36, sheen at 0x37, and
the requested species at 0x38. Verified against each ROM's table, located
by its first nickname: FireRed's "MIMIEN" Mr. Mime asks for Abra, and
Emerald's "DOTS" Seedot asks for Ralts.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

from .text import decode_gen3_text

INGAME_TRADE_SIZE = 60
_NAME_SIZE = 11


@dataclass(frozen=True, slots=True)
class Gen3InGameTrade:
    nickname: str
    species_id: int
    ivs: tuple[int, ...]
    ability_slot: int
    ot_id: int
    conditions: tuple[int, ...]
    personality: int
    held_item_id: int
    ot_name: str
    ot_gender: int
    sheen: int
    requested_species_id: int


def parse_ingame_trade(data: bytes) -> Gen3InGameTrade:
    if len(data) != INGAME_TRADE_SIZE:
        raise InvalidRomError(
            f"Gen III in-game trade has size {len(data)}, expected {INGAME_TRADE_SIZE}"
        )
    species_id, *ivs = struct.unpack_from("<H6B", data, 0x0C)
    return Gen3InGameTrade(
        nickname=decode_gen3_text(data[:_NAME_SIZE]),
        species_id=species_id,
        ivs=tuple(ivs),
        ability_slot=data[0x14],
        ot_id=struct.unpack_from("<I", data, 0x18)[0],
        conditions=tuple(data[0x1C:0x21]),
        personality=struct.unpack_from("<I", data, 0x24)[0],
        held_item_id=struct.unpack_from("<H", data, 0x28)[0],
        ot_name=decode_gen3_text(data[0x2B : 0x2B + _NAME_SIZE]),
        ot_gender=data[0x36],
        sheen=data[0x37],
        requested_species_id=struct.unpack_from("<H", data, 0x38)[0],
    )
