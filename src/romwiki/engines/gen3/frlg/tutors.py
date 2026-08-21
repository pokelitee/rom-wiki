from __future__ import annotations

import struct
from collections.abc import Mapping

from romwiki.schema import ShardCosts, TutorCompatibility, TutorMove
from romwiki.util.errors import InvalidRomError

from .constants import MAX_MOVE_ID, TUTOR_LOCATIONS, TUTOR_MOVE_COUNT

# Renumbers the 4 tutors in TUTOR_LOCATIONS (see constants.py) to
# sequential 1-based tutor IDs, the shape `validate_tutors` expects.
TUTOR_ID_BY_TABLE_INDEX = {
    table_index: rank + 1 for rank, table_index in enumerate(sorted(TUTOR_LOCATIONS))
}


def parse_tutor_move_table(
    data: bytes, *, location_ids: Mapping[int, int]
) -> tuple[TutorMove, ...]:
    """Decode `gTutorMoves`. `location_ids` must map each exposed tutor's
    table index (`TUTOR_LOCATIONS`' keys) to that specific ROM's own
    `header_id` for its target region -- resolved by the extraction layer
    against this ROM's own decoded location names, not read from
    `TUTOR_LOCATIONS` directly (see its comment for why).
    """
    expected_size = TUTOR_MOVE_COUNT * 2
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III tutor move table has size {len(data)}, expected {expected_size}"
        )
    records = []
    for table_index in sorted(TUTOR_LOCATIONS):
        (move_id,) = struct.unpack_from("<H", data, table_index * 2)
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen III tutor {table_index} has invalid move ID {move_id}"
            )
        records.append(
            TutorMove(
                tutor_id=TUTOR_ID_BY_TABLE_INDEX[table_index],
                move_id=move_id,
                # Genuinely free -- no shard-like cost mechanic exists.
                shard_costs=ShardCosts(0, 0, 0, 0),
                location_id=location_ids[table_index],
                table_index=table_index,
            )
        )
    return tuple(records)


def parse_tutor_compatibility(
    data: bytes, *, species_id: int, table_index: int
) -> TutorCompatibility | None:
    """Decode one species' 2-byte `sTutorLearnsets` bitmask, keeping only
    the 4 exposed tutors. Returns `None` if none apply.
    """
    if len(data) != 2:
        raise InvalidRomError(
            f"Gen III tutor compatibility for species {species_id} has size "
            f"{len(data)}, expected 2"
        )
    (bits,) = struct.unpack("<H", data)
    tutor_ids = tuple(
        TUTOR_ID_BY_TABLE_INDEX[index]
        for index in sorted(TUTOR_LOCATIONS)
        if bits & (1 << index)
    )
    if not tutor_ids:
        return None
    return TutorCompatibility(
        personal_member=species_id, tutor_ids=tutor_ids, table_index=table_index
    )
