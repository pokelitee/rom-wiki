"""B2W2 overworld-object records without BW trainer-ID arithmetic."""

from __future__ import annotations

import struct
from dataclasses import dataclass

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
