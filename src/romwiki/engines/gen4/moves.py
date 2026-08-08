from __future__ import annotations

import struct

from romwiki.schema import Move, RecordProvenance
from romwiki.util.errors import InvalidRomError

MOVE_RECORD_SIZE = 16


def parse_move_record(
    data: bytes,
    *,
    move_id: int,
    archive_path: str,
) -> Move:
    if len(data) != MOVE_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV move record {move_id} has size {len(data)}, "
            f"expected {MOVE_RECORD_SIZE}"
        )

    effect_id, target_id = struct.unpack_from("<H6xH", data)
    padding = struct.unpack_from("<H", data, 14)[0]
    if padding != 0:
        raise InvalidRomError(
            f"Gen IV move record {move_id} has nonzero padding: {padding}"
        )

    return Move(
        move_id=move_id,
        effect_id=effect_id,
        damage_class_id=data[2],
        power=data[3],
        type_id=data[4],
        accuracy=data[5],
        pp=data[6],
        effect_chance=data[7],
        target_id=target_id,
        priority=struct.unpack_from("<b", data, 10)[0],
        flags=data[11],
        contest_effect_id=data[12],
        contest_type_id=data[13],
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=move_id,
        ),
    )

