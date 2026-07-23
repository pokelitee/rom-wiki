from __future__ import annotations

import struct

from romwiki.schema import Gen4LevelUpLearnset, LevelUpMove, RecordProvenance
from romwiki.util.errors import InvalidRomError

LEARNSET_TERMINATOR = 0xFFFF
MOVE_ID_MASK = 0x01FF
LEVEL_SHIFT = 9


def parse_level_up_learnset(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> Gen4LevelUpLearnset:
    if len(data) < 2 or len(data) % 2:
        raise InvalidRomError(
            f"Gen IV learnset record {species_id} has invalid size {len(data)}"
        )

    values = tuple(value[0] for value in struct.iter_unpack("<H", data))
    try:
        terminator_index = values.index(LEARNSET_TERMINATOR)
    except ValueError as error:
        raise InvalidRomError(
            f"Gen IV learnset record {species_id} has no terminator"
        ) from error

    trailing = values[terminator_index + 1 :]
    if trailing not in ((), (0,)):
        raise InvalidRomError(
            f"Gen IV learnset record {species_id} has invalid trailing data"
        )

    moves = tuple(
        LevelUpMove(level=value >> LEVEL_SHIFT, move_id=value & MOVE_ID_MASK)
        for value in values[:terminator_index]
    )
    return Gen4LevelUpLearnset(
        species_id=species_id,
        moves=moves,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
