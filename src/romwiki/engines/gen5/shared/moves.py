from __future__ import annotations

import struct

from romwiki.engines.gen5.shared.constants import MOVE_RECORD_SIZE
from romwiki.schema import Move, RecordProvenance
from romwiki.util.errors import InvalidRomError


def parse_move_record(
    data: bytes,
    *,
    move_id: int,
    archive_path: str,
) -> Move:
    if len(data) != MOVE_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V move record {move_id} has size {len(data)}, "
            f"expected {MOVE_RECORD_SIZE}"
        )

    effect_id = struct.unpack_from("<H", data, 16)[0]
    flags = struct.unpack_from("<I", data, 32)[0]

    return Move(
        move_id=move_id,
        effect_id=effect_id,
        damage_class_id=data[2],
        power=data[3],
        type_id=data[0],
        accuracy=data[4],
        pp=data[5],
        effect_chance=data[10],
        target_id=data[20],
        priority=struct.unpack_from("<b", data, 6)[0],
        flags=flags,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=move_id,
        ),
    )
