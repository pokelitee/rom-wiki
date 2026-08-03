from __future__ import annotations

import struct
from dataclasses import dataclass

# `a/1/2/5`: one member per map header (`layout.map_headers`'s own record
# index, confirmed 1:1 -- see below), holding that map's furniture/NPC/warp/
# trigger placements. Record layout adopted from
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

# NPCs whose sight-triggered battle is dispatched through a shared/common
# script reference their trainer with `script_used = band + trainer_id`,
# where `band` is a multiple of 1000 (seen: 2000/3000/5000/7000 in the real
# ROM). Verified against 18 real Black ROM trainer records this way (script
# member 155 and 830's NPCs resolving to trainer IDs 26-34 and 40-48, both
# consecutive runs with sensible ascending trainer classes/party sizes) --
# not literal script-engine facts, but arithmetic on an already-decoded NPC
# field, matching this project's "decode, don't guess" bar since every
# resolved ID is checked against the real trainer table's own valid range.
_COMMON_SCRIPT_BAND_SIZE = 1000
_MIN_COMMON_SCRIPT_USED = _COMMON_SCRIPT_BAND_SIZE
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


# Visible field items are NPC objects using one specific, shared sprite ID
# (the item-ball graphic) whose `script_used` is a flat `7000 + item_id`
# offset -- verified against the real Black ROM: sprite 110 is by far the
# most common NPC sprite in the game (274 uses, next-most-common is 92),
# and every one of its `script_used - 7000` values resolves to a real,
# coherent field-pickup item (Hyper Potion, Fire Stone, Full Restore, HP Up,
# evolution stones, vitamins, berries -- exactly what routes actually give
# you), never a garbage/unnamed slot.
_VISIBLE_ITEM_SPRITE = 110
_VISIBLE_ITEM_SCRIPT_BASE = 7000

# Hidden items (found via the Dowsing MCHN) are furniture entries whose
# `script_used` is a flat `8000 + item_id` offset -- verified the same way:
# every real furniture entry with `script_used >= 8000` resolves to a real,
# well-known hidden-item fact (Odd Keystone, the four Drives, Adamant Orb,
# the fossils hidden around Desert Resort/Relic Castle -- all real,
# well-documented Black/White hidden items).
_HIDDEN_ITEM_SCRIPT_BASE = 8000


def resolve_visible_item_id(npc: Gen5OverworldNPC, *, item_count: int) -> int | None:
    """Resolve a field NPC to the item it represents, if it's an item ball."""
    if npc.sprite != _VISIBLE_ITEM_SPRITE:
        return None
    item_id = npc.script_used - _VISIBLE_ITEM_SCRIPT_BASE
    if not 0 < item_id < item_count:
        return None
    return item_id


def resolve_hidden_item_id(
    furniture: Gen5OverworldFurniture, *, item_count: int
) -> int | None:
    """Resolve a furniture entry to the hidden item it represents, if any."""
    item_id = furniture.script_used - _HIDDEN_ITEM_SCRIPT_BASE
    if not 0 < item_id < item_count:
        return None
    return item_id


def resolve_common_script_trainer_id(
    script_used: int, *, trainer_count: int
) -> int | None:
    """Resolve a sight-triggered NPC's `script_used` to a literal trainer ID.

    Returns `None` for local per-map script indices (`script_used` below the
    common-script band) or for values that don't resolve to a real trainer
    record, rather than guessing.
    """
    if script_used < _MIN_COMMON_SCRIPT_USED:
        return None
    band = (script_used // _COMMON_SCRIPT_BAND_SIZE) * _COMMON_SCRIPT_BAND_SIZE
    trainer_id = script_used - band
    if not 0 < trainer_id < trainer_count:
        return None
    return trainer_id


def resolve_common_script_member(
    script_used: int, *, member_count: int
) -> int | None:
    """Resolve a 10xxx overworld script reference to its archive member."""
    if script_used < _COMMON_SCRIPT_REFERENCE_BASE:
        return None
    member = COMMON_SCRIPT_MEMBER_BASE + script_used - _COMMON_SCRIPT_REFERENCE_BASE
    return member if member < member_count else None
