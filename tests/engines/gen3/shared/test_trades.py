from __future__ import annotations

import struct

import pytest

from romwiki.engines.gen3.shared.trades import INGAME_TRADE_SIZE, parse_ingame_trade
from romwiki.util.errors import InvalidRomError


def _text(value: str) -> bytes:
    return bytes(0xBB + ord(letter) - ord("A") for letter in value) + b"\xff"


def test_parses_an_ingame_trade() -> None:
    data = bytearray(INGAME_TRADE_SIZE)
    data[0:5] = _text("DOTS")
    struct.pack_into("<H6BB", data, 0x0C, 298, 5, 4, 5, 4, 4, 4, 1)
    struct.pack_into("<I5B", data, 0x18, 38726, 30, 5, 5, 5, 5)
    struct.pack_into("<IHB", data, 0x24, 0x84, 141, 0xFF)
    data[0x2B:0x30] = _text("KOBE")
    struct.pack_into("<BBH", data, 0x36, 0, 10, 392)

    trade = parse_ingame_trade(bytes(data))

    assert (trade.nickname, trade.species_id, trade.requested_species_id) == (
        "DOTS",
        298,
        392,
    )
    assert trade.ivs == (5, 4, 5, 4, 4, 4)
    assert (trade.ot_name, trade.ot_id, trade.held_item_id) == ("KOBE", 38726, 141)
    assert (trade.conditions, trade.sheen, trade.personality) == (
        (30, 5, 5, 5, 5),
        10,
        0x84,
    )


def test_rejects_a_short_record() -> None:
    with pytest.raises(InvalidRomError):
        parse_ingame_trade(b"\x00" * 59)
