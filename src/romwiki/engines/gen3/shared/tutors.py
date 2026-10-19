from __future__ import annotations

import struct
from collections.abc import Mapping

from romwiki.schema import ShardCosts, TutorCompatibility, TutorMove
from romwiki.util.errors import InvalidRomError

from .constants import MAX_MOVE_ID

# `gTutorMoves` lists one move per tutor, and `sTutorLearnsets` holds one
# little-endian bitmask per species (bit N = tutor N). FireRed/LeafGreen have
# 15 tutors and 2-byte masks; Emerald appends 15 more and widens the masks to
# 4 bytes. Each leaf binds its own table size and `TUTOR_LOCATIONS`.


def parse_tutor_move_table(
    data: bytes,
    *,
    location_ids: Mapping[int, int],
    tutor_locations: Mapping[int, str],
    tutor_count: int,
) -> tuple[TutorMove, ...]:
    """Decode `gTutorMoves`, keeping the tutors in `tutor_locations`.

    `location_ids` must map each kept tutor's table index to that specific
    ROM's own `header_id` for its target region -- resolved by the
    extraction layer against this ROM's own decoded location names.
    """
    expected_size = tutor_count * 2
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III tutor move table has size {len(data)}, expected {expected_size}"
        )
    tutor_ids = _tutor_ids(tutor_locations)
    records = []
    for table_index in sorted(tutor_locations):
        (move_id,) = struct.unpack_from("<H", data, table_index * 2)
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen III tutor {table_index} has invalid move ID {move_id}"
            )
        records.append(
            TutorMove(
                tutor_id=tutor_ids[table_index],
                move_id=move_id,
                # Genuinely free -- no shard-like cost mechanic exists.
                shard_costs=ShardCosts(0, 0, 0, 0),
                location_id=location_ids[table_index],
                table_index=table_index,
            )
        )
    return tuple(records)


def parse_tutor_compatibility(
    data: bytes,
    *,
    species_id: int,
    table_index: int,
    tutor_locations: Mapping[int, str],
    record_size: int,
) -> TutorCompatibility | None:
    """Decode one species' `sTutorLearnsets` bitmask, keeping only the tutors
    in `tutor_locations`. Returns `None` if none apply.
    """
    if len(data) != record_size:
        raise InvalidRomError(
            f"Gen III tutor compatibility for species {species_id} has size "
            f"{len(data)}, expected {record_size}"
        )
    bits = int.from_bytes(data, "little")
    tutor_ids = _tutor_ids(tutor_locations)
    compatible = tuple(
        tutor_ids[index] for index in sorted(tutor_locations) if bits & (1 << index)
    )
    if not compatible:
        return None
    return TutorCompatibility(
        personal_member=species_id, tutor_ids=compatible, table_index=table_index
    )


def _tutor_ids(tutor_locations: Mapping[int, str]) -> dict[int, int]:
    # Sequential 1-based tutor IDs, the shape `validate_tutors` expects.
    return {
        table_index: rank + 1
        for rank, table_index in enumerate(sorted(tutor_locations))
    }
