from __future__ import annotations

import struct

from romwiki.schema import LevelUpLearnset, LevelUpMove, RecordProvenance
from romwiki.util.errors import InvalidRomError

# `gLevelUpLearnsets`: one GBA pointer per personal record, each to a u16
# array of `level << 9 | move ID` entries ended by 0xFFFF -- the encoding
# Generation IV also uses. Verified on FireRed, LeafGreen, and Emerald
# (Bulbasaur: Tackle at 1, Growl at 4, Leech Seed at 7). Entry 0 points at
# Bulbasaur's learnset, and every placeholder species 252-276 at a lone Tackle.
LEARNSET_POINTER_SIZE = 4
LEARNSET_TERMINATOR = 0xFFFF
MOVE_ID_MASK = 0x01FF
LEVEL_SHIFT = 9
# Bytes read past each pointer: room for 127 moves and the terminator, more
# than any retail learnset or a hack's longer ones need.
LEARNSET_READ_SIZE = 256


def parse_level_up_learnset(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> LevelUpLearnset:
    """Decode one learnset from `data`, which starts at the learnset's pointer
    target and may run past its terminator."""
    moves: list[LevelUpMove] = []
    for (value,) in struct.iter_unpack("<H", data[: len(data) // 2 * 2]):
        if value == LEARNSET_TERMINATOR:
            return LevelUpLearnset(
                species_id=species_id,
                moves=tuple(moves),
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=species_id
                ),
            )
        moves.append(
            LevelUpMove(level=value >> LEVEL_SHIFT, move_id=value & MOVE_ID_MASK)
        )
    raise InvalidRomError(
        f"Gen III learnset {species_id} has no terminator within {len(data)} bytes"
    )
