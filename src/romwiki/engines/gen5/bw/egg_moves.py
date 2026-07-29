from __future__ import annotations

import struct

from romwiki.schema import Gen5EggMoveSet, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import MAX_MOVE_ID


def parse_egg_move_set(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> Gen5EggMoveSet:
    if not data:
        # Member 0 is an unused placeholder record (empty), the same as the
        # personal-data archive's own member 0.
        return Gen5EggMoveSet(
            species_id=species_id,
            move_ids=(),
            provenance=RecordProvenance(
                source="rom",
                archive=archive_path,
                member=species_id,
            ),
        )
    if len(data) < 2 or len(data) % 2:
        raise InvalidRomError(
            f"Gen V egg move record {species_id} has invalid size {len(data)}"
        )
    count = struct.unpack_from("<H", data, 0)[0]
    if len(data) != 2 + count * 2:
        raise InvalidRomError(
            f"Gen V egg move record {species_id} count {count} does not match "
            f"its size {len(data)}"
        )
    move_ids = struct.unpack_from(f"<{count}H", data, 2) if count else ()
    for move_id in move_ids:
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen V egg move record {species_id} has invalid move ID {move_id}"
            )
    return Gen5EggMoveSet(
        species_id=species_id,
        move_ids=move_ids,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
