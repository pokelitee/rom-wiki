from __future__ import annotations

import struct

from romwiki.schema import LevelUpLearnset, LevelUpMove, RecordProvenance
from romwiki.util.errors import InvalidRomError

LEARNSET_TERMINATOR = (0xFFFF, 0xFFFF)


def parse_level_up_learnset(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> LevelUpLearnset:
    if len(data) < 4 or len(data) % 4:
        raise InvalidRomError(
            f"Gen V learnset record {species_id} has invalid size {len(data)}"
        )

    moves = []
    for offset in range(0, len(data), 4):
        move_id, level = struct.unpack_from("<HH", data, offset)
        if (move_id, level) == LEARNSET_TERMINATOR:
            return LevelUpLearnset(
                species_id=species_id,
                moves=tuple(moves),
                provenance=RecordProvenance(
                    source="rom",
                    archive=archive_path,
                    member=species_id,
                ),
            )
        if move_id == 0:
            # Move zero is the engine's "none" sentinel. Blaze Black/Volt
            # White leave three such disabled entries at the start of
            # Whimsicott's edited learnset.
            continue
        moves.append(LevelUpMove(level=level, move_id=move_id))

    raise InvalidRomError(f"Gen V learnset record {species_id} has no terminator")
