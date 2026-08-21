from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

# Generation III's overworld-object/script system (`struct MapEvents`,
# `struct ObjectEventTemplate`, public pokefirered decompilation
# `include/global.fieldmap.h`), verified against the real FireRed and
# LeafGreen ROMs: decoding all 124 already-known Sevii Islands/postgame map
# headers' `events` pointers found 75 real trainer object events whose
# script bytes start with the `trainerbattle` opcode (0x5c) and decode to
# trainer IDs entirely within the valid 0-742 range (`TRAINER_RECORD_COUNT`)
# -- e.g. trainer IDs 89/90/105-107/116-119 clustered on one map, matching a
# real gym-style room layout, and a double-battle pair (two objects sharing
# the same trainer ID 484, `battle_type=4` = `TRAINER_BATTLE_DOUBLE`).
#
# `MapEvents` (20 bytes):
#   0x00  objectEventCount (u8)
#   0x01  warpCount (u8)
#   0x02  coordEventCount (u8)
#   0x03  bgEventCount (u8)
#   0x04  objectEvents pointer (u32 GBA ROM address)
#   0x08  warps pointer (not decoded this pass)
#   0x0C  coordEvents pointer (not decoded this pass)
#   0x10  bgEvents pointer (not decoded this pass)
MAP_EVENTS_SIZE = 20

# `ObjectEventTemplate` (24 bytes, one per overworld object on a map):
#   0x00  localId (u8)
#   0x01  graphicsId (u8, not decoded)
#   0x02  kind (u8) -- 0 = "normal" (the union fields below apply); any
#         other value is a "clone" object (a duplicate NPC mirroring
#         another map's object) with a different union layout, not decoded
#         here since it can't itself be a trainer battle trigger
#   0x03  padding
#   0x04  x (s16), 0x06 y (s16)
#   0x08  elevation (u8), 0x09 movementType (u8, not decoded)
#   0x0A  movementRangeX:4 / movementRangeY:4 (u16 bitfield, not decoded)
#   0x0C  trainerType (u16) -- 0 = not a trainer
#   0x0E  trainerRange_berryTreeId (u16, not decoded)
#   0x10  script pointer (u32 GBA ROM address)
#   0x14  flagId (u16, not decoded)
OBJECT_EVENT_TEMPLATE_SIZE = 24

# The `trainerbattle` script command (`asm/macros/event.inc` in the public
# decompilation): opcode 0x5c, then a 1-byte battle type, then a 2-byte
# trainer ID (LE u16) -- the only two fields this module needs; the
# variable-length text/event-script pointers that follow (depending on
# battle type) aren't decoded.
_TRAINERBATTLE_OPCODE = 0x5C


def parse_map_events(data: bytes, *, header_id: int) -> tuple[int, int]:
    """Decode a 20-byte `MapEvents` struct into `(object_event_count,
    object_events_pointer)`. Only the object-event count/pointer are needed
    for trainer-location backfill; warp/coord/bg-event fields exist in the
    struct but aren't decoded by this module.
    """
    if len(data) != MAP_EVENTS_SIZE:
        raise InvalidRomError(
            f"Gen III map events for header {header_id} has size {len(data)}, "
            f"expected {MAP_EVENTS_SIZE}"
        )
    object_event_count = data[0]
    object_events_pointer = struct.unpack_from("<I", data, 0x04)[0]
    return object_event_count, object_events_pointer


def parse_object_event_template(
    data: bytes, *, header_id: int, index: int
) -> tuple[int, int, int, int, int, int, int]:
    """Decode a 24-byte `ObjectEventTemplate` into `(local_id, kind, x, y,
    elevation, trainer_type, script_pointer)`.

    `kind != 0` ("clone") reuses the same byte layout for a different
    union, so `trainer_type`/`script_pointer` are only meaningful when
    `kind == 0`; callers must check that themselves before trusting either
    field.
    """
    if len(data) != OBJECT_EVENT_TEMPLATE_SIZE:
        raise InvalidRomError(
            f"Gen III object event {index} for header {header_id} has size "
            f"{len(data)}, expected {OBJECT_EVENT_TEMPLATE_SIZE}"
        )
    local_id, kind = data[0], data[2]
    x, y = struct.unpack_from("<hh", data, 0x04)
    elevation = data[0x08]
    trainer_type = struct.unpack_from("<H", data, 0x0C)[0]
    script_pointer = struct.unpack_from("<I", data, 0x10)[0]
    return local_id, kind, x, y, elevation, trainer_type, script_pointer


def decode_trainerbattle_id(data: bytes) -> int | None:
    """Decode a script's leading `trainerbattle` command, if present.

    `data` must be at least 4 bytes read from the object event's script
    pointer. Returns the trainer ID (u16 LE at byte offset 2) if the script
    begins with the `trainerbattle` opcode (0x5c), else `None` -- an object
    event with `trainer_type != 0` whose script does something else first
    (e.g. a rematch-eligibility check) isn't decoded by this pass.
    """
    if len(data) < 4 or data[0] != _TRAINERBATTLE_OPCODE:
        return None
    return struct.unpack_from("<H", data, 2)[0]
