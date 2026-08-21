from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError


@dataclass(frozen=True, slots=True)
class Gen4FossilRevival:
    item_id: int
    species_id: int


def parse_fossil_revival_table(
    data: bytes, *, offset: int, count: int, item_count: int, species_count: int
) -> tuple[Gen4FossilRevival, ...]:
    size = count * 4
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError("Fossil revival table is outside the ROM image")
    entries = []
    for index in range(count):
        item_id, species_id = struct.unpack_from("<HH", data, offset + index * 4)
        if not 0 < item_id < item_count:
            raise InvalidRomError(
                f"Fossil revival table references invalid item {item_id}"
            )
        if not 0 < species_id < species_count:
            raise InvalidRomError(
                f"Fossil revival table references invalid species {species_id}"
            )
        entries.append(Gen4FossilRevival(item_id=item_id, species_id=species_id))
    return tuple(entries)
