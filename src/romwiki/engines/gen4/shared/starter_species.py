from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

#: Each starter is stored as a full word, not a species-sized halfword: the
#: accessor returns them through pc-relative word loads, one per branch of an
#: index switch.
STARTER_SPECIES_ENTRY_SIZE = 4


def parse_starter_species(
    data: bytes, *, count: int, species_count: int
) -> tuple[int, ...]:
    """Decode the species the game's starter accessor can return.

    The three constants are reached individually by a switch on the starter
    index, so they are validated as species rather than assumed: a region that
    does not hold `count` distinct in-range species is not this table, and
    decoding fails rather than supplying a wrong starter set.
    """
    expected = count * STARTER_SPECIES_ENTRY_SIZE
    if len(data) != expected:
        raise InvalidRomError(
            f"Gen IV starter species table has size {len(data)}; expected {expected}"
        )

    species = struct.unpack(f"<{count}I", data)
    for value in species:
        if not 0 < value < species_count:
            raise InvalidRomError(
                f"Gen IV starter species table contains invalid species {value}"
            )
    if len(set(species)) != len(species):
        raise InvalidRomError("Gen IV starter species table repeats a species")
    return species
