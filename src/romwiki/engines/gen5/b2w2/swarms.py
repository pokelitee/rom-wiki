from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.schema import RecordProvenance
from romwiki.util.errors import InvalidRomError

SWARM_RECORD_SIZE = 8


@dataclass(frozen=True, slots=True)
class SwarmEncounter:
    header_id: int
    species_id: int
    minimum_level: int
    maximum_level: int
    table_offset: int
    provenance: RecordProvenance


def parse_swarm_table(
    data: bytes,
    *,
    record_count: int,
    archive_path: str,
    table_offset: int,
    map_header_count: int,
    species_count: int,
) -> tuple[SwarmEncounter, ...]:
    expected_size = record_count * SWARM_RECORD_SIZE
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Swarm table has size {len(data)}, expected {expected_size}"
        )

    records = []
    seen_headers: set[int] = set()
    for index in range(record_count):
        offset = index * SWARM_RECORD_SIZE
        values = struct.unpack_from("<HHBBBB", data, offset)
        (
            header_id,
            species_id,
            leading_padding,
            minimum_level,
            maximum_level,
            trailing_padding,
        ) = values
        if not 0 <= header_id < map_header_count:
            raise InvalidRomError(
                f"Swarm record {index} references invalid map header {header_id}"
            )
        if header_id in seen_headers:
            raise InvalidRomError(
                f"Swarm table references map header {header_id} more than once"
            )
        if not 0 < species_id < species_count:
            raise InvalidRomError(
                f"Swarm record {index} references invalid species {species_id}"
            )
        if not 0 < minimum_level <= maximum_level <= 100:
            raise InvalidRomError(
                f"Swarm record {index} has invalid level range "
                f"{minimum_level}-{maximum_level}"
            )
        if leading_padding or trailing_padding:
            raise InvalidRomError(f"Swarm record {index} has nonzero padding")
        seen_headers.add(header_id)
        records.append(
            SwarmEncounter(
                header_id=header_id,
                species_id=species_id,
                minimum_level=minimum_level,
                maximum_level=maximum_level,
                table_offset=table_offset + offset,
                provenance=RecordProvenance(
                    source="rom",
                    archive=archive_path,
                    member=index,
                ),
            )
        )
    return tuple(records)


__all__ = ["SWARM_RECORD_SIZE", "SwarmEncounter", "parse_swarm_table"]
