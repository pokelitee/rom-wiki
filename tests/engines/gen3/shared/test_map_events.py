from __future__ import annotations

import struct

import pytest

from romwiki.engines.gen3.shared.map_events import (
    decode_packed_hidden_item,
    decode_split_hidden_item,
    parse_bg_event,
    parse_coord_event_script,
    parse_gba_map_events,
    parse_map_connection,
    parse_map_connections,
    parse_warp_event,
)
from romwiki.util.errors import InvalidRomError


def test_map_events_counts_and_pointers() -> None:
    events = parse_gba_map_events(struct.pack("<4B4I", 1, 2, 3, 4, 10, 20, 30, 40))

    assert (events.object_count, events.warp_count) == (1, 2)
    assert (events.coord_count, events.bg_count) == (3, 4)
    assert events.bgs_pointer == 40


def test_warp_event_reads_map_num_before_map_group() -> None:
    warp = parse_warp_event(struct.pack("<hh4B", 5, 6, 3, 1, 19, 3))

    assert (warp.x, warp.y, warp.warp_id) == (5, 6, 1)
    assert (warp.map_group, warp.map_num) == (3, 19)


def test_coord_and_bg_events() -> None:
    coord = struct.pack("<HHBxHHxxI", 1, 2, 3, 4, 5, 0x08001234)
    assert parse_coord_event_script(coord) == 0x08001234

    sign = parse_bg_event(struct.pack("<HHBBxxI", 7, 8, 0, 7, 0x00120056))
    assert (sign.x, sign.y, sign.kind, sign.value) == (7, 8, 7, 0x00120056)


def test_hidden_item_packing_differs_by_game() -> None:
    # FireRed/LeafGreen: item, flag offset, quantity (7 bits), underfoot.
    packed = 0x0D | (0x21 << 16) | (3 << 24) | (1 << 31)
    assert decode_packed_hidden_item(packed) == (0x0D, 3, 0x21)
    # Emerald: u16 item, u16 flag; always one.
    assert decode_split_hidden_item(0x01F4_0044) == (0x44, 1, 0x01F4)


def test_connections() -> None:
    assert parse_map_connections(struct.pack("<iI", 2, 0x08000100)) == (2, 0x08000100)
    connection = parse_map_connection(struct.pack("<BxxxiBBxx", 2, -10, 3, 19))
    assert connection is not None
    assert (connection.direction, connection.map_group, connection.map_num) == (
        "north",
        3,
        19,
    )
    assert parse_map_connection(struct.pack("<BxxxiBBxx", 9, 0, 0, 0)) is None


def test_rejects_wrong_sizes() -> None:
    with pytest.raises(InvalidRomError):
        parse_warp_event(b"\x00" * 7)
