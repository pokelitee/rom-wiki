from __future__ import annotations

import struct

from romwiki.schema import EvolutionEntry, Gen4EvolutionSet, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import (
    EVOLUTION_RECORD_SIZE,
    EVOLUTION_SLOT_COUNT,
    EVOLUTION_SLOT_SIZE,
)


def parse_evolution_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> Gen4EvolutionSet:
    if len(data) != EVOLUTION_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V evolution record {species_id} has size {len(data)}, "
            f"expected {EVOLUTION_RECORD_SIZE}"
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
        if method_id == 0:
            # The game treats method zero as disabled regardless of the two
            # operands. Blaze Black/Volt White leave Feebas's former evolution
            # operands in such a slot before adding its replacement method.
            continue
        if target_species_id == 0:
            raise InvalidRomError(
                f"Gen V evolution record {species_id} has incomplete slot {slot}"
            )
        if found_empty_slot:
            raise InvalidRomError(
                f"Gen V evolution record {species_id} has data after an empty slot"
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
