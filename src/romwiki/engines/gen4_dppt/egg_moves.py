from __future__ import annotations

import struct

from romwiki.schema import Gen4EggMoveSet
from romwiki.util.errors import InvalidRomError

EGG_MOVE_TABLE_TERMINATOR = 0xFFFF
EGG_MOVE_SPECIES_MARKER_BASE = 20000
GEN4_MAX_SPECIES_ID = 493
GEN4_MAX_MOVE_ID = 467


def parse_egg_move_table(
    data: bytes, *, table_offset: int = 0
) -> tuple[Gen4EggMoveSet, ...]:
    if table_offset < 0 or table_offset % 2 or table_offset + 2 > len(data):
        raise InvalidRomError("Gen IV egg move table has an invalid offset")

    records = []
    species_id: int | None = None
    move_ids: list[int] = []
    marker_offset = table_offset
    cursor = table_offset
    while cursor + 2 <= len(data):
        value = struct.unpack_from("<H", data, cursor)[0]
        cursor += 2
        if value == EGG_MOVE_TABLE_TERMINATOR:
            if species_id is None:
                raise InvalidRomError("Gen IV egg move table is empty")
            _append_record(records, species_id, move_ids, marker_offset)
            return tuple(records)

        if (
            EGG_MOVE_SPECIES_MARKER_BASE
            < value
            <= (EGG_MOVE_SPECIES_MARKER_BASE + GEN4_MAX_SPECIES_ID)
        ):
            next_species_id = value - EGG_MOVE_SPECIES_MARKER_BASE
            if species_id is not None:
                _append_record(records, species_id, move_ids, marker_offset)
                if next_species_id <= species_id:
                    raise InvalidRomError(
                        "Gen IV egg move species markers are not ordered"
                    )
            species_id = next_species_id
            move_ids = []
            marker_offset = cursor - 2
            continue

        if species_id is None:
            raise InvalidRomError("Gen IV egg move table does not start with a species")
        if not 1 <= value <= GEN4_MAX_MOVE_ID:
            raise InvalidRomError(f"Gen IV egg move table has invalid move ID {value}")
        if value in move_ids:
            raise InvalidRomError("Gen IV egg move set contains duplicate moves")
        move_ids.append(value)

    raise InvalidRomError("Gen IV egg move table has no terminator")


def _append_record(
    records: list[Gen4EggMoveSet],
    species_id: int,
    move_ids: list[int],
    overlay_offset: int,
) -> None:
    if not move_ids:
        raise InvalidRomError(f"Gen IV egg move species {species_id} has no moves")
    records.append(
        Gen4EggMoveSet(
            species_id=species_id,
            move_ids=tuple(move_ids),
            table_index=len(records),
            overlay_offset=overlay_offset,
        )
    )
