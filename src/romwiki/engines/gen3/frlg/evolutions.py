from __future__ import annotations

import struct

from romwiki.schema import EvolutionEntry, EvolutionSet, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import EVOLUTION_RECORD_SIZE, EVOLUTION_SLOT_COUNT, EVOLUTION_SLOT_SIZE


def parse_evolution_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> EvolutionSet:
    if len(data) != EVOLUTION_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen III evolution record {species_id} has size {len(data)}, "
            f"expected {EVOLUTION_RECORD_SIZE}"
        )

    evolutions = []
    for slot in range(EVOLUTION_SLOT_COUNT):
        method_id, parameter, target_species_id = struct.unpack_from(
            "<HHH", data, slot * EVOLUTION_SLOT_SIZE
        )
        if method_id == 0:
            # An empty slot, or (per Gen V's identical convention) a method
            # explicitly disabled while operands are still present -- either
            # way, not a real evolution.
            continue
        if target_species_id == 0:
            raise InvalidRomError(
                f"Gen III evolution record {species_id} has incomplete slot {slot}"
            )
        evolutions.append(
            EvolutionEntry(
                method_id=method_id,
                parameter=parameter,
                target_species_id=target_species_id,
            )
        )

    return EvolutionSet(
        species_id=species_id,
        evolutions=tuple(evolutions),
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
