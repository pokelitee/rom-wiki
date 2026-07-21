from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError
from romwiki.schema import (
    Gen4SpecialTutorMove,
    Gen4TutorCompatibility,
    Gen4TutorMove,
    ShardCosts,
)


TUTOR_RECORD_SIZE = 12
TUTOR_COMPATIBILITY_RECORD_SIZE = 5
SET_VAR_FROM_VALUE = 0x0028
COMPARE_VAR_TO_VALUE = 0x0011
GO_TO = 0x0016
GO_TO_IF = 0x001C
SPECIAL_TUTOR_MOVE_VAR = 0x8003
SPECIAL_TUTOR_SPECIES_VAR = 0x8001


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


def parse_special_tutor_move(
    data: bytes,
    *,
    tutor_id: int,
    script_member: int,
    command_offset: int,
    map_header_id: int,
    location_name: str,
    eligibility_kind: str,
    eligibility_value: int | tuple[int, ...],
    minimum_friendship: int,
) -> Gen4SpecialTutorMove:
    if command_offset < 0 or command_offset + 8 > len(data):
        raise InvalidRomError("Gen IV special tutor command is outside its script")
    opcode, destination, move_id, next_opcode = struct.unpack_from(
        "<4H", data, command_offset
    )
    if (
        opcode != SET_VAR_FROM_VALUE
        or destination != SPECIAL_TUTOR_MOVE_VAR
        or next_opcode != GO_TO
    ):
        raise InvalidRomError("Gen IV special tutor command has an invalid signature")
    if not 1 <= move_id <= 467:
        raise InvalidRomError(f"Gen IV special tutor has invalid move ID {move_id}")
    if eligibility_kind not in {"species", "type"}:
        raise InvalidRomError("Gen IV special tutor has an unknown eligibility rule")
    if eligibility_kind == "type" and (
        not isinstance(eligibility_value, int) or not 0 <= eligibility_value <= 17
    ):
        raise InvalidRomError("Gen IV special tutor has an invalid type rule")
    if eligibility_kind == "species" and (
        not isinstance(eligibility_value, tuple) or not eligibility_value
    ):
        raise InvalidRomError("Gen IV special tutor has an invalid species rule")
    if not 0 <= minimum_friendship <= 255:
        raise InvalidRomError("Gen IV special tutor has invalid friendship metadata")
    return Gen4SpecialTutorMove(
        tutor_id=tutor_id,
        move_id=move_id,
        location_name=location_name,
        eligibility_kind=eligibility_kind,
        eligibility_value=eligibility_value,
        minimum_friendship=minimum_friendship,
        script_member=script_member,
        command_offset=command_offset,
        map_header_id=map_header_id,
    )


def parse_special_tutor_species(
    data: bytes, *, comparison_offset: int, species_count: int
) -> tuple[int, ...]:
    if species_count <= 0:
        raise InvalidRomError("Gen IV special tutor species count is invalid")
    species_ids = []
    cursor = comparison_offset
    for index in range(species_count):
        if cursor < 0 or cursor + 13 > len(data):
            raise InvalidRomError("Gen IV special tutor species list is truncated")
        opcode, variable, species_id = struct.unpack_from("<3H", data, cursor)
        branch_opcode = struct.unpack_from("<H", data, cursor + 6)[0]
        condition = data[cursor + 8]
        if (
            opcode != COMPARE_VAR_TO_VALUE
            or variable != SPECIAL_TUTOR_SPECIES_VAR
            or branch_opcode != GO_TO_IF
            or condition != 1
            or not 1 <= species_id <= 493
        ):
            raise InvalidRomError(
                f"Gen IV special tutor species comparison {index} is invalid"
            )
        species_ids.append(species_id)
        cursor += 13
    if len(species_ids) != len(set(species_ids)):
        raise InvalidRomError("Gen IV special tutor species list contains duplicates")
    return tuple(species_ids)
