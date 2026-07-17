from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.errors import InvalidRomError


@dataclass(frozen=True, slots=True)
class Gen4ObjectEvent:
    index: int
    local_id: int
    graphics_id: int
    movement_type: int
    trainer_type: int
    hidden_flag: int
    script_id: int
    direction: int
    data: tuple[int, int, int]
    movement_range_x: int
    movement_range_z: int
    x: int
    z: int
    y: int


@dataclass(frozen=True, slots=True)
class Gen4WarpEvent:
    index: int
    x: int
    z: int
    destination_header_id: int
    destination_warp_id: int


@dataclass(frozen=True, slots=True)
class Gen4MapEvents:
    objects: tuple[Gen4ObjectEvent, ...]
    warps: tuple[Gen4WarpEvent, ...]


def parse_map_events(data: bytes, *, event_file_id: int) -> Gen4MapEvents:
    position = 0
    background_count, position = _read_count(data, position, event_file_id)
    position = _skip_records(data, position, background_count, 20, event_file_id)
    object_count, position = _read_count(data, position, event_file_id)
    object_end = _skip_records(data, position, object_count, 32, event_file_id)

    objects = []
    for index in range(object_count):
        values = struct.unpack_from("<6Hh3HhhHHi", data, position + index * 32)
        objects.append(
            Gen4ObjectEvent(
                index=index,
                local_id=values[0],
                graphics_id=values[1],
                movement_type=values[2],
                trainer_type=values[3],
                hidden_flag=values[4],
                script_id=values[5],
                direction=values[6],
                data=values[7:10],
                movement_range_x=values[10],
                movement_range_z=values[11],
                x=values[12],
                z=values[13],
                y=values[14],
            )
        )

    position = object_end
    warp_count, position = _read_count(data, position, event_file_id)
    warp_end = _skip_records(data, position, warp_count, 12, event_file_id)
    warps = []
    for index in range(warp_count):
        x, z, destination_header_id, destination_warp_id, unused_1, unused_2 = (
            struct.unpack_from("<6H", data, position + index * 12)
        )
        if unused_1 or unused_2:
            raise InvalidRomError(
                f"Event file {event_file_id} warp {index} has nonzero unused data"
            )
        warps.append(
            Gen4WarpEvent(
                index=index,
                x=x,
                z=z,
                destination_header_id=destination_header_id,
                destination_warp_id=destination_warp_id,
            )
        )
    position = warp_end
    coordinate_count, position = _read_count(data, position, event_file_id)
    position = _skip_records(data, position, coordinate_count, 16, event_file_id)
    if position != len(data):
        raise InvalidRomError(
            f"Event file {event_file_id} has {len(data) - position} trailing bytes"
        )
    return Gen4MapEvents(objects=tuple(objects), warps=tuple(warps))


def parse_object_events(
    data: bytes, *, event_file_id: int
) -> tuple[Gen4ObjectEvent, ...]:
    return parse_map_events(data, event_file_id=event_file_id).objects


def parse_warp_events(data: bytes, *, event_file_id: int) -> tuple[Gen4WarpEvent, ...]:
    return parse_map_events(data, event_file_id=event_file_id).warps


def _read_count(data: bytes, position: int, event_file_id: int) -> tuple[int, int]:
    if position + 4 > len(data):
        raise InvalidRomError(f"Event file {event_file_id} is truncated")
    return struct.unpack_from("<I", data, position)[0], position + 4


def _skip_records(
    data: bytes, position: int, count: int, size: int, event_file_id: int
) -> int:
    end = position + count * size
    if end > len(data):
        raise InvalidRomError(f"Event file {event_file_id} record table is truncated")
    return end
