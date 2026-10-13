from __future__ import annotations

import struct

from romwiki.engines.gen3.shared.constants import MOVE_RECORD_SIZE
from romwiki.schema import Move, RecordProvenance
from romwiki.util.errors import InvalidRomError

# Generation III's move struct (`gBattleMoves` in the public pokefirered/
# pokeemerald decompilations) is a fixed 12-byte record, verified against
# the real FireRed and LeafGreen ROMs (move 1 Pound, move 2 Karate Chop,
# move 33 Tackle, move 34 Body Slam all decode to their known real stats):
#   0x00  effect ID
#   0x01  power
#   0x02  type ID
#   0x03  accuracy
#   0x04  pp
#   0x05  secondary effect chance
#   0x06  target ID
#   0x07  priority (signed)
#   0x08-0x0B  flags bitmap (u32)
# Unlike Generation IV/V, there is no separate damage-class (physical/
# special/status) byte and no Contest-related fields in this struct.
# Generation I-III determine damage class purely from the move's type (a
# fixed type-to-category table, not a per-move flag) except that any move
# with power 0 is a status move regardless of type -- see
# `_PHYSICAL_TYPE_IDS` below.

# Type IDs matching `constants.py`'s TYPE_NAMES ordering. Physical types are
# every type that was physical for its entire Generation I-III lifetime;
# every other type (Fire/Water/Grass/Electric/Psychic/Ice/Dragon/Dark) was
# special. The one type with no real moves in this era (9, "unknown"/???,
# used only by Curse) defaults to special below since it isn't a listed
# physical type -- Curse has power 0, so it's classified as status anyway
# before this fallback is reached.
_PHYSICAL_TYPE_IDS = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8})


def parse_move_record(
    data: bytes,
    *,
    move_id: int,
    archive_path: str,
) -> Move:
    if len(data) != MOVE_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen III move record {move_id} has size {len(data)}, "
            f"expected {MOVE_RECORD_SIZE}"
        )

    power = data[1]
    type_id = data[2]
    if power == 0:
        damage_class_id = 0
    elif type_id in _PHYSICAL_TYPE_IDS:
        damage_class_id = 1
    else:
        damage_class_id = 2

    return Move(
        move_id=move_id,
        effect_id=data[0],
        damage_class_id=damage_class_id,
        power=power,
        type_id=type_id,
        accuracy=data[3],
        pp=data[4],
        effect_chance=data[5],
        target_id=data[6],
        priority=struct.unpack_from("<b", data, 7)[0],
        flags=struct.unpack_from("<I", data, 8)[0],
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=move_id,
        ),
    )
