from __future__ import annotations

import struct

from romwiki.schema import ShardCosts, TutorCompatibility, TutorMove
from romwiki.util.errors import InvalidRomError

TUTOR_COUNT = 60
TUTOR_RECORD_SIZE = 12
TUTOR_COMPATIBILITY_OFFSET = 60
TUTOR_LOCATION_NAMES = (
    "Humilau City",
    "Driftveil City",
    "Lentimas Town",
    "Nacrene City",
)
_MOVE_GROUP_COUNTS = (13, 15, 15, 17)
_MOVE_GROUP_SHARDS = ("yellow", "red", "blue", "green")
_PERSONAL_GROUP_COUNTS = (15, 17, 13, 15)
_PERSONAL_TO_MOVE_GROUP = (1, 3, 0, 2)


def parse_tutor_move_table(data: bytes) -> tuple[TutorMove, ...]:
    if len(data) != TUTOR_COUNT * TUTOR_RECORD_SIZE:
        raise InvalidRomError("B2W2 tutor move table has an invalid size")
    boundaries = tuple(
        sum(_MOVE_GROUP_COUNTS[: index + 1]) for index in range(len(_MOVE_GROUP_COUNTS))
    )
    records = []
    for index in range(TUTOR_COUNT):
        move_id, cost = struct.unpack_from("<II", data, index * 12)
        group = next(
            group for group, boundary in enumerate(boundaries) if index < boundary
        )
        costs = {
            color: cost if color == _MOVE_GROUP_SHARDS[group] else 0
            for color in ("red", "blue", "yellow", "green")
        }
        records.append(
            TutorMove(
                tutor_id=index + 1,
                move_id=move_id,
                shard_costs=ShardCosts(**costs),
                location_id=group,
                table_index=index,
            )
        )
    return tuple(records)


def parse_tutor_compatibility_record(
    data: bytes, *, personal_member: int
) -> TutorCompatibility:
    end = TUTOR_COMPATIBILITY_OFFSET + 16
    if len(data) < end:
        raise InvalidRomError(
            f"B2W2 personal member {personal_member} has no tutor flags"
        )
    move_starts = tuple(
        sum(_MOVE_GROUP_COUNTS[:group]) for group in range(len(_MOVE_GROUP_COUNTS))
    )
    tutor_ids: list[int] = []
    for personal_group, count in enumerate(_PERSONAL_GROUP_COUNTS):
        offset = TUTOR_COMPATIBILITY_OFFSET + personal_group * 4
        mask = int.from_bytes(data[offset : offset + 4], "little")
        move_start = move_starts[_PERSONAL_TO_MOVE_GROUP[personal_group]]
        tutor_ids.extend(
            move_start + bit + 1 for bit in range(count) if mask & (1 << bit)
        )
    return TutorCompatibility(
        personal_member=personal_member,
        tutor_ids=tuple(sorted(tutor_ids)),
        table_index=personal_member,
    )
