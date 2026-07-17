from __future__ import annotations

import struct

from romwiki.errors import InvalidRomError
from romwiki.schema import Gen4TutorCompatibility, Gen4TutorMove, ShardCosts


TUTOR_RECORD_SIZE = 12
TUTOR_COMPATIBILITY_RECORD_SIZE = 5


def parse_tutor_move_table(
    data: bytes, *, tutor_count: int
) -> tuple[Gen4TutorMove, ...]:
    if tutor_count <= 0 or len(data) != tutor_count * TUTOR_RECORD_SIZE:
        raise InvalidRomError("Gen IV tutor move table has an invalid size")
    records = []
    for index in range(tutor_count):
        offset = index * TUTOR_RECORD_SIZE
        move_id, red, blue, yellow, green = struct.unpack_from("<H4B", data, offset)
        padding = data[offset + 6 : offset + 8]
        location_id = struct.unpack_from("<I", data, offset + 8)[0]
        if not 1 <= move_id <= 467:
            raise InvalidRomError(
                f"Gen IV tutor {index + 1} has invalid move ID {move_id}"
            )
        if padding != b"\0\0":
            raise InvalidRomError(f"Gen IV tutor {index + 1} has nonzero padding")
        records.append(
            Gen4TutorMove(
                tutor_id=index + 1,
                move_id=move_id,
                shard_costs=ShardCosts(red, blue, yellow, green),
                location_id=location_id,
                table_index=index,
            )
        )
    return tuple(records)


def parse_tutor_compatibility_table(
    data: bytes,
    *,
    tutor_count: int,
    base_species_count: int,
    form_member_start: int,
    form_count: int,
) -> tuple[Gen4TutorCompatibility, ...]:
    record_count = base_species_count + form_count
    if tutor_count <= 0 or tutor_count > TUTOR_COMPATIBILITY_RECORD_SIZE * 8:
        raise InvalidRomError("Gen IV tutor compatibility configuration is invalid")
    if (
        base_species_count <= 0
        or form_member_start <= base_species_count
        or form_count < 0
    ):
        raise InvalidRomError("Gen IV tutor species mapping is invalid")
    if len(data) != record_count * TUTOR_COMPATIBILITY_RECORD_SIZE:
        raise InvalidRomError("Gen IV tutor compatibility table has an invalid size")

    records = []
    valid_mask = (1 << tutor_count) - 1
    for index in range(record_count):
        offset = index * TUTOR_COMPATIBILITY_RECORD_SIZE
        mask = int.from_bytes(
            data[offset : offset + TUTOR_COMPATIBILITY_RECORD_SIZE], "little"
        )
        if mask & ~valid_mask:
            raise InvalidRomError(
                f"Gen IV tutor compatibility row {index} has unknown tutor bits"
            )
        personal_member = index + 1
        if index >= base_species_count:
            personal_member = form_member_start + index - base_species_count
        records.append(
            Gen4TutorCompatibility(
                personal_member=personal_member,
                tutor_ids=tuple(
                    tutor_id
                    for tutor_id in range(1, tutor_count + 1)
                    if mask & (1 << (tutor_id - 1))
                ),
                table_index=index,
            )
        )
    return tuple(records)
