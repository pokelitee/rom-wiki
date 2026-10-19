"""Generation III map events and connections.

Struct layouts follow pret/pokefirered's and pret/pokeemerald's
`include/global.fieldmap.h`, identical in both games except how a hidden
item packs its fields (see each leaf's `decode_hidden_item`).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

# `struct MapEvents`: four u8 counts, then pointers to the object, warp,
# coordinate, and background ("sign") event arrays.
GBA_MAP_EVENTS_SIZE = 20
# `struct WarpEvent`: s16 x, s16 y, u8 elevation, u8 warpId, u8 mapNum,
# u8 mapGroup.
WARP_EVENT_SIZE = 8
# `struct CoordEvent`: u16 x, u16 y, u8 elevation, padding, u16 trigger,
# u16 index, padding, script pointer at 0x0C.
COORD_EVENT_SIZE = 16
# `struct BgEvent`: u16 x, u16 y, u8 elevation, u8 kind, padding, then a
# u32 union at 0x08: a script pointer, or a hidden item when kind is
# `BG_EVENT_HIDDEN_ITEM`.
BG_EVENT_SIZE = 12
BG_EVENT_HIDDEN_ITEM = 7
# Kinds 0-4 are signs read from a given facing; the union is a script.
BG_EVENT_SCRIPT_KINDS = frozenset(range(5))
# `struct MapConnections`: s32 count, connection-array pointer.
MAP_CONNECTIONS_SIZE = 8
# `struct MapConnection`: u8 direction, padding, s32 offset at 0x04,
# u8 mapGroup at 0x08, u8 mapNum at 0x09, padding.
MAP_CONNECTION_SIZE = 12
CONNECTION_DIRECTIONS = {
    1: "south",
    2: "north",
    3: "west",
    4: "east",
    5: "dive",
    6: "emerge",
}
# A warp whose destination is `MAP_DYNAMIC` leads wherever the player last
# came from.
DYNAMIC_MAP = (0x7F, 0x7F)


@dataclass(frozen=True, slots=True)
class GbaMapEvents:
    object_count: int
    warp_count: int
    coord_count: int
    bg_count: int
    objects_pointer: int
    warps_pointer: int
    coords_pointer: int
    bgs_pointer: int


@dataclass(frozen=True, slots=True)
class GbaWarpEvent:
    x: int
    y: int
    elevation: int
    warp_id: int
    map_group: int
    map_num: int


@dataclass(frozen=True, slots=True)
class GbaBgEvent:
    x: int
    y: int
    elevation: int
    kind: int
    value: int


@dataclass(frozen=True, slots=True)
class GbaMapConnection:
    direction: str
    map_group: int
    map_num: int


def parse_gba_map_events(data: bytes) -> GbaMapEvents:
    _require_size(data, GBA_MAP_EVENTS_SIZE, "map events")
    return GbaMapEvents(*struct.unpack("<4B4I", data))


def parse_warp_event(data: bytes) -> GbaWarpEvent:
    _require_size(data, WARP_EVENT_SIZE, "warp event")
    x, y, elevation, warp_id, map_num, map_group = struct.unpack("<hh4B", data)
    return GbaWarpEvent(x, y, elevation, warp_id, map_group, map_num)


def parse_coord_event_script(data: bytes) -> int:
    """Return a `CoordEvent`'s script pointer (0 when it has none)."""
    _require_size(data, COORD_EVENT_SIZE, "coordinate event")
    return int(struct.unpack_from("<I", data, 0x0C)[0])


def parse_bg_event(data: bytes) -> GbaBgEvent:
    _require_size(data, BG_EVENT_SIZE, "background event")
    x, y, elevation, kind, value = struct.unpack("<HHBBxxI", data)
    return GbaBgEvent(x, y, elevation, kind, value)


def parse_map_connections(data: bytes) -> tuple[int, int]:
    """Decode `MapConnections` into `(count, connections_pointer)`."""
    _require_size(data, MAP_CONNECTIONS_SIZE, "map connections")
    count, pointer = struct.unpack("<iI", data)
    if count < 0:
        raise InvalidRomError(f"Gen III map connections have count {count}")
    return count, pointer


def parse_map_connection(data: bytes) -> GbaMapConnection | None:
    """Decode one `MapConnection`, or `None` for an unknown direction."""
    _require_size(data, MAP_CONNECTION_SIZE, "map connection")
    direction = CONNECTION_DIRECTIONS.get(data[0])
    if direction is None:
        return None
    return GbaMapConnection(direction, data[0x08], data[0x09])


def decode_packed_hidden_item(value: int) -> tuple[int, int, int]:
    """FireRed/LeafGreen hidden item: item (bits 0-15), flag offset from
    `FLAG_HIDDEN_ITEMS_START` (16-23), quantity (24-30), and an underfoot
    bit (31). Returns `(item_id, quantity, flag)`.
    """
    return value & 0xFFFF, (value >> 24) & 0x7F, (value >> 16) & 0xFF


def decode_split_hidden_item(value: int) -> tuple[int, int, int]:
    """Emerald hidden item: u16 item, then u16 `hiddenItemId` flag; always
    one of the item. Returns `(item_id, quantity, flag)`.
    """
    return value & 0xFFFF, 1, value >> 16


def _require_size(data: bytes, size: int, label: str) -> None:
    if len(data) != size:
        raise InvalidRomError(f"Gen III {label} has size {len(data)}, expected {size}")
