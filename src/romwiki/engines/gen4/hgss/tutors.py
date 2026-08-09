from __future__ import annotations

import struct

from romwiki.schema import BattlePointTutorMove, TutorCompatibility
from romwiki.util.errors import InvalidRomError

TUTOR_COUNT = 52
TUTOR_RECORD_SIZE = 4
TUTOR_COMPATIBILITY_RECORD_SIZE = 8
TUTOR_LOCATION_NAMES = (
    "Frontier Front",
    "Frontier Front",
    "Frontier Front",
    "Ilex Forest",
)


def parse_tutor_move_table(data: bytes) -> tuple[BattlePointTutorMove, ...]:
    if len(data) != TUTOR_COUNT * TUTOR_RECORD_SIZE:
        raise InvalidRomError("HGSS tutor move table has an invalid size")

    records = []
    for index in range(TUTOR_COUNT):
        move_id, packed_cost = struct.unpack_from("<HH", data, index * 4)
        battle_point_cost = packed_cost & 0xFF
        location_id = packed_cost >> 8
        if not 1 <= move_id <= 467:
            raise InvalidRomError(
                f"HGSS tutor {index + 1} has invalid move ID {move_id}"
            )
        if battle_point_cost not in {0, 32, 40, 48, 64}:
            raise InvalidRomError(
                f"HGSS tutor {index + 1} has invalid BP cost {battle_point_cost}"
            )
        if location_id >= len(TUTOR_LOCATION_NAMES):
            raise InvalidRomError(
                f"HGSS tutor {index + 1} has invalid location ID {location_id}"
            )
        if location_id == 3 and (move_id != 29 or battle_point_cost != 0):
            raise InvalidRomError("HGSS Ilex Forest tutor record is invalid")
        records.append(
            BattlePointTutorMove(
                tutor_id=index + 1,
                move_id=move_id,
                battle_point_cost=battle_point_cost,
                location_id=location_id,
                table_index=index,
            )
        )
    return tuple(records)


def parse_tutor_compatibility_table(
    data: bytes,
    *,
    base_species_count: int,
    form_member_start: int,
    form_count: int,
) -> tuple[TutorCompatibility, ...]:
    record_count = base_species_count + form_count
    if (
        base_species_count <= 0
        or form_member_start <= base_species_count
        or form_count < 0
    ):
        raise InvalidRomError("HGSS tutor species mapping is invalid")
    if len(data) != record_count * TUTOR_COMPATIBILITY_RECORD_SIZE:
        raise InvalidRomError("HGSS tutor compatibility table has an invalid size")

    records = []
    valid_mask = (1 << TUTOR_COUNT) - 1
    for index in range(record_count):
        offset = index * TUTOR_COMPATIBILITY_RECORD_SIZE
        mask = int.from_bytes(
            data[offset : offset + TUTOR_COMPATIBILITY_RECORD_SIZE], "little"
        )
        if mask & ~valid_mask:
            raise InvalidRomError(
                f"HGSS tutor compatibility row {index} has unknown tutor bits"
            )
        personal_member = index + 1
        if index >= base_species_count:
            personal_member = form_member_start + index - base_species_count
        records.append(
            TutorCompatibility(
                personal_member=personal_member,
                tutor_ids=tuple(
                    tutor_id
                    for tutor_id in range(1, TUTOR_COUNT + 1)
                    if mask & (1 << (tutor_id - 1))
                ),
                table_index=index,
            )
        )
    return tuple(records)
