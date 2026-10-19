from __future__ import annotations

import struct

from romwiki.engines.gen3.shared.constants import LAST_SPECIES_ID, MAX_MOVE_ID
from romwiki.schema import OverlayEggMoveSet
from romwiki.util.errors import InvalidRomError

# `gEggMoves[]`: a single flat u16 array, not indexed by species -- each
# species' block starts with a marker `species_id + 20000`, followed by
# move IDs, until the next marker or the `0xFFFF` terminator. Same scheme
# as Generation IV (`gen4/egg_moves.py`, which this mirrors).
EGG_MOVE_TABLE_TERMINATOR = 0xFFFF
EGG_MOVE_SPECIES_MARKER_BASE = 20000


def parse_egg_move_table(
    data: bytes, *, table_offset: int = 0
) -> tuple[OverlayEggMoveSet, ...]:
    if table_offset < 0 or table_offset % 2 or table_offset + 2 > len(data):
        raise InvalidRomError("Gen III egg move table has an invalid offset")

    entries: list[tuple[int, tuple[int, ...], int]] = []
    species_id: int | None = None
    move_ids: list[int] = []
    marker_offset = table_offset
    cursor = table_offset
    while cursor + 2 <= len(data):
        value = struct.unpack_from("<H", data, cursor)[0]
        cursor += 2
        if value == EGG_MOVE_TABLE_TERMINATOR:
            if species_id is None:
                raise InvalidRomError("Gen III egg move table is empty")
            _append_entry(entries, species_id, move_ids, marker_offset)
            return _egg_move_sets(entries)

        if (
            EGG_MOVE_SPECIES_MARKER_BASE
            < value
            <= (EGG_MOVE_SPECIES_MARKER_BASE + LAST_SPECIES_ID)
        ):
            next_species_id = value - EGG_MOVE_SPECIES_MARKER_BASE
            if species_id is not None:
                _append_entry(entries, species_id, move_ids, marker_offset)
                if next_species_id <= species_id:
                    raise InvalidRomError(
                        "Gen III egg move species markers are not ordered"
                    )
            species_id = next_species_id
            move_ids = []
            marker_offset = cursor - 2
            continue

        if species_id is None:
            raise InvalidRomError(
                "Gen III egg move table does not start with a species"
            )
        if not 1 <= value <= MAX_MOVE_ID:
            raise InvalidRomError(f"Gen III egg move table has invalid move ID {value}")
        move_ids.append(value)

    raise InvalidRomError("Gen III egg move table has no terminator")


def _append_entry(
    entries: list[tuple[int, tuple[int, ...], int]],
    species_id: int,
    move_ids: list[int],
    table_offset: int,
) -> None:
    if not move_ids:
        raise InvalidRomError(f"Gen III egg move species {species_id} has no moves")
    entries.append((species_id, tuple(move_ids), table_offset))


def _egg_move_sets(
    entries: list[tuple[int, tuple[int, ...], int]],
) -> tuple[OverlayEggMoveSet, ...]:
    return tuple(
        OverlayEggMoveSet(
            species_id=species_id,
            move_ids=move_ids,
            table_index=table_index,
            overlay_offset=table_offset,
        )
        for table_index, (species_id, move_ids, table_offset) in enumerate(entries)
    )
