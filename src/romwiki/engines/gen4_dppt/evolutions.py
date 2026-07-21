from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError
from romwiki.schema import EvolutionEntry, Gen4EvolutionSet, RecordProvenance


EVOLUTION_RECORD_SIZE = 44
EVOLUTION_SLOT_COUNT = 7
EVOLUTION_SLOT_SIZE = 6


def parse_evolution_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> Gen4EvolutionSet:
    if len(data) != EVOLUTION_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV evolution record {species_id} has size {len(data)}, "
            f"expected {EVOLUTION_RECORD_SIZE}"
        )
    padding = struct.unpack_from("<H", data, EVOLUTION_SLOT_COUNT * EVOLUTION_SLOT_SIZE)[0]
    if padding:
        raise InvalidRomError(
            f"Gen IV evolution record {species_id} has nonzero padding: {padding}"
        )

    evolutions = []
    found_empty_slot = False
    for slot in range(EVOLUTION_SLOT_COUNT):
        method_id, parameter, target_species_id = struct.unpack_from(
            "<3H", data, slot * EVOLUTION_SLOT_SIZE
        )
        if method_id == parameter == target_species_id == 0:
            found_empty_slot = True
            continue
        if method_id == 0 or target_species_id == 0:
            raise InvalidRomError(
                f"Gen IV evolution record {species_id} has incomplete slot {slot}"
            )
        if found_empty_slot:
            raise InvalidRomError(
                f"Gen IV evolution record {species_id} has data after an empty slot"
            )
        evolutions.append(
            EvolutionEntry(
                method_id=method_id,
                parameter=parameter,
                target_species_id=target_species_id,
            )
        )

    return Gen4EvolutionSet(
        species_id=species_id,
        evolutions=tuple(evolutions),
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
