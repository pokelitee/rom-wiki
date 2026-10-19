from __future__ import annotations

from collections.abc import Mapping

from romwiki.engines.gen3.shared import tutors as shared
from romwiki.schema import TutorCompatibility, TutorMove

from .constants import TUTOR_COMPATIBILITY_SIZE, TUTOR_LOCATIONS, TUTOR_MOVE_COUNT


def parse_tutor_move_table(
    data: bytes, *, location_ids: Mapping[int, int]
) -> tuple[TutorMove, ...]:
    return shared.parse_tutor_move_table(
        data,
        location_ids=location_ids,
        tutor_locations=TUTOR_LOCATIONS,
        tutor_count=TUTOR_MOVE_COUNT,
    )


def parse_tutor_compatibility(
    data: bytes, *, species_id: int, table_index: int
) -> TutorCompatibility | None:
    return shared.parse_tutor_compatibility(
        data,
        species_id=species_id,
        table_index=table_index,
        tutor_locations=TUTOR_LOCATIONS,
        record_size=TUTOR_COMPATIBILITY_SIZE,
    )
