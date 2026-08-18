from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass

from romwiki.engines.gen5.trainer_records import (
    resolve_common_script_trainer_id as resolve_common_script_trainer_id,
)

# `a/1/2/5`: one member per overworld event set, holding that map's
# furniture/NPC/warp/trigger placements. BW happens to use header IDs as
# member IDs; B2W2 stores a separate member index in each map header. Record
# layout adopted from
# FrostFalcon/FrostsGen5Editor's `OverworldObjectsNARC.cs` and verified
# against real Black ROM data: for three different maps, the highest
# `scriptUsed` value among that map's own NPCs (1-indexed) exactly matched
# the number of local script functions in that map's own dedicated script
# file (23/15/22 functions, matching NPC `scriptUsed` maxima of 23/15/22
# exactly, for three unrelated maps) -- not a coincidence across three
# independent samples.
_HEADER_SIZE = 8
_NPC_RECORD_SIZE = 36
_NPC_FIELD_NAMES = (
    "id",
    "sprite",
    "movement_permissions",
    "permissions2",
    "flag",
    "script_used",
    "default_direction",
    "sight_range",
    "unknown1",
    "unknown2",
    "horizontal_leash",
    "vertical_leash",
    "unknown3",
    "unknown4",
    "x",
    "y",
    "unknown5",
    "z",
)

COMMON_SCRIPT_MEMBER_BASE = 442
_COMMON_SCRIPT_REFERENCE_BASE = 10000


@dataclass(frozen=True, slots=True)
class Gen5OverworldNPC:
    index: int
    sprite: int
    flag: int
    script_used: int
    sight_range: int
    x: int
    y: int
    z: int


def parse_overworld_npcs(data: bytes) -> tuple[Gen5OverworldNPC, ...]:
    if len(data) <= _HEADER_SIZE:
        return ()
    furniture_count = data[4]
    npc_count = data[5]
    pos = _HEADER_SIZE + furniture_count * 20
    npcs = []
    for index in range(npc_count):
        if pos + _NPC_RECORD_SIZE > len(data):
            break
        values = struct.unpack_from(f"<{len(_NPC_FIELD_NAMES)}h", data, pos)
        fields = dict(zip(_NPC_FIELD_NAMES, values, strict=True))
        npcs.append(
            Gen5OverworldNPC(
                index=index,
                sprite=fields["sprite"],
                flag=fields["flag"],
                script_used=fields["script_used"],
                sight_range=fields["sight_range"],
                x=fields["x"],
                y=fields["y"],
                z=fields["z"],
            )
        )
        pos += _NPC_RECORD_SIZE
    return tuple(npcs)


_FURNITURE_RECORD_SIZE = 20
# Unlike every other overworld record's plain-integer coordinates, furniture's
# own `x` field is stored in 16.16 fixed point -- found by comparing raw
# values against the same map's own NPCs: a hidden item's raw `x` divided by
# this scale lands in the exact same magnitude range as that map's NPCs'
# plain-integer x coordinates, across five unrelated real maps (e.g. map 6's
# furniture x values of 744-801 versus its own NPCs' 752-792). `y`/`z` are
# already plain integers at the same scale as NPCs' own, with no such
# conversion needed.
_FURNITURE_X_FIXED_POINT_SCALE = 65536


@dataclass(frozen=True, slots=True)
class Gen5OverworldFurniture:
    index: int
    script_used: int
    x: int
    y: int
    z: int


def parse_overworld_furniture(data: bytes) -> tuple[Gen5OverworldFurniture, ...]:
    if len(data) <= _HEADER_SIZE:
        return ()
    furniture_count = data[4]
    pos = _HEADER_SIZE
    items = []
    for index in range(furniture_count):
        if pos + _FURNITURE_RECORD_SIZE > len(data):
            break
        script_used = struct.unpack_from("<h", data, pos)[0]
        x = struct.unpack_from("<i", data, pos + 6)[0] // _FURNITURE_X_FIXED_POINT_SCALE
        y = struct.unpack_from("<i", data, pos + 12)[0]
        z = struct.unpack_from("<i", data, pos + 16)[0]
        items.append(
            Gen5OverworldFurniture(index=index, script_used=script_used, x=x, y=y, z=z)
        )
        pos += _FURNITURE_RECORD_SIZE
    return tuple(items)


_WARP_RECORD_SIZE = 20


@dataclass(frozen=True, slots=True)
class Gen5OverworldWarp:
    index: int
    destination_header_id: int
    destination_warp_id: int
    x: int
    y: int
    z: int


def parse_overworld_warps(data: bytes) -> tuple[Gen5OverworldWarp, ...]:
    """Parse a map's warp placements (`OverworldWarp` in FrostFalcon's source).

    `destination_header_id`/`destination_warp_id` are verified against real
    Black ROM data: checking every warp in the game for reciprocity (does the
    destination map's own warp at `destination_warp_id` point back to this
    map?) matches for 858 of 873 real warps -- the remainder are real,
    expected one-way warps (holes, ledges, slides), not a decoding error.
    """
    if len(data) <= _HEADER_SIZE:
        return ()
    furniture_count = data[4]
    npc_count = data[5]
    warp_count = data[6]
    pos = _HEADER_SIZE + furniture_count * 20 + npc_count * _NPC_RECORD_SIZE
    warps = []
    for index in range(warp_count):
        if pos + _WARP_RECORD_SIZE > len(data):
            break
        dest_header, dest_warp = struct.unpack_from("<hh", data, pos)
        x, y, z = struct.unpack_from("<hhh", data, pos + 8)
        warps.append(
            Gen5OverworldWarp(
                index=index,
                destination_header_id=dest_header,
                destination_warp_id=dest_warp,
                x=x,
                y=y,
                z=z,
            )
        )
        pos += _WARP_RECORD_SIZE
    return tuple(warps)


# Visible field items are NPC objects using the item-ball sprite. Their
# `script_used` value selects a function in the shared item-ball script member;
# it is not itself an item ID. Hidden furniture uses the equivalent hidden-item
# script member. Each selected function stores the actual item as a literal.
_VISIBLE_ITEM_SPRITE = 110
_VISIBLE_ITEM_SCRIPT_BASE = 7000
_HIDDEN_ITEM_SCRIPT_BASE = 8000
_SCRIPT_LIST_TERMINATOR = 0xFD13
_VISIBLE_ITEM_SET_COMMAND = 0x28
_VISIBLE_ITEM_VARIABLE = 0x800C
_HIDDEN_ITEM_SET_COMMAND = 0x2A
_HIDDEN_ITEM_VARIABLE = 0x8000


def _parse_field_item_script_table(
    data: bytes, *, set_command: int, variable: int
) -> tuple[int | None, ...]:
    """Decode item literals while preserving their shared-script indices."""
    if len(data) < 4:
        return ()
    first_function = 4 + struct.unpack_from("<I", data)[0]
    entries: list[int | None] = []
    offset = 0
    while offset + 4 <= len(data) and offset < first_function:
        if struct.unpack_from("<H", data, offset)[0] == _SCRIPT_LIST_TERMINATOR:
            break
        function = offset + 4 + struct.unpack_from("<I", data, offset)[0]
        if function + 8 > len(data):
            entries.append(None)
        else:
            command, work, item_id = struct.unpack_from("<HHH", data, function + 2)
            entries.append(
                item_id if (command, work) == (set_command, variable) else None
            )
        offset += 4
    return tuple(entries)


def parse_visible_item_script_table(data: bytes) -> tuple[int | None, ...]:
    return _parse_field_item_script_table(
        data, set_command=_VISIBLE_ITEM_SET_COMMAND, variable=_VISIBLE_ITEM_VARIABLE
    )


def parse_hidden_item_script_table(data: bytes) -> tuple[int | None, ...]:
    return _parse_field_item_script_table(
        data, set_command=_HIDDEN_ITEM_SET_COMMAND, variable=_HIDDEN_ITEM_VARIABLE
    )


def resolve_visible_item_id(
    npc: Gen5OverworldNPC,
    *,
    item_count: int,
    item_ids: Sequence[int | None] = (),
) -> int | None:
    """Resolve a field NPC to the item it represents, if it's an item ball."""
    if npc.sprite != _VISIBLE_ITEM_SPRITE:
        return None
    index = npc.script_used - _VISIBLE_ITEM_SCRIPT_BASE - 1
    if not 0 <= index < len(item_ids):
        return None
    item_id = item_ids[index]
    return item_id if item_id is not None and 0 < item_id < item_count else None


def resolve_hidden_item_id(
    furniture: Gen5OverworldFurniture,
    *,
    item_count: int,
    item_ids: Sequence[int | None] = (),
) -> int | None:
    """Resolve a furniture entry to the hidden item it represents, if any."""
    index = furniture.script_used - _HIDDEN_ITEM_SCRIPT_BASE - 1
    if not 0 <= index < len(item_ids):
        return None
    item_id = item_ids[index]
    return item_id if item_id is not None and 0 < item_id < item_count else None


def resolve_common_script_member(script_used: int, *, member_count: int) -> int | None:
    """Resolve a 10xxx overworld script reference to its archive member."""
    if script_used < _COMMON_SCRIPT_REFERENCE_BASE:
        return None
    member = COMMON_SCRIPT_MEMBER_BASE + script_used - _COMMON_SCRIPT_REFERENCE_BASE
    return member if member < member_count else None
