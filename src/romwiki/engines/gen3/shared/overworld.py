from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

# Generation III's overworld-object/script system (`struct MapEvents`,
# `struct ObjectEventTemplate`, public pokefirered/pokeemerald
# decompilation `include/global.fieldmap.h`). Verified against both real
# ROMs: decoding every already-known FireRed/LeafGreen Sevii Islands/
# postgame map's `events` pointer found 75 real trainer object events whose
# scripts start with the `trainerbattle` opcode and decode to valid
# trainer IDs (0-742), including a real double-battle pair sharing one
# trainer ID; decoding every already-known Emerald map's `events` pointer
# (across its own `map_header_segments`) found 441 real trainer object
# events whose scripts decode to valid Emerald trainer IDs matching real
# trainer names (CALVIN, RICK, TIANA, DAISY, ...) -- confirming the same
# 20/24-byte struct shapes, unchanged.
MAP_EVENTS_SIZE = 20  # objectEventCount(u8) + ... + objectEvents ptr @0x04

# 0x02 kind: 0 = "normal" object (fields below apply); nonzero = "clone"
# (a different union layout, can't be a trainer). trainerType @0x0C, script
# pointer @0x10.
OBJECT_EVENT_TEMPLATE_SIZE = 24

# `trainerbattle` script command: opcode 0x5c, 1-byte battle type, then a
# 2-byte trainer ID -- the only fields this module needs.
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
