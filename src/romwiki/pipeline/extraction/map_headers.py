"""Shared code-binary and map-header table reading, used by every extractor
that resolves in-game location names (encounters, trainers, locations, tutors).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from romwiki.util.errors import DataSourceError, InvalidRomError


def read_code_binary(platform: Any, image: Any, *, compressed: bool = False) -> bytes:
    """Read the platform's main code binary (the ARM9 blob on Nintendo DS).

    `compressed` selects the decompressing reader for engines whose code
    binary is stored compressed.
    """
    if compressed:
        if platform.read_decompressed_code_binary is None:
            raise DataSourceError(
                "The selected platform does not expose a decompressed code binary"
            )
        return platform.read_decompressed_code_binary(image)
    if platform.read_code_binary is None:
        raise DataSourceError("The selected platform does not expose a code binary")
    return platform.read_code_binary(image)


def code_load_address(platform: Any, image: Any) -> int:
    """Return the memory address the platform loads its code binary at."""
    if platform.code_load_address is None:
        raise DataSourceError(
            "The selected platform does not expose a code load address"
        )
    return platform.code_load_address(image)


def parse_map_header_table(
    engine: Any,
    arm9_data: bytes,
    filesystem: Any,
    map_names_path: str,
    *,
    table_offset: int,
    count: int,
) -> tuple[Any, ...]:
    """Parse the map header table at `table_offset` within an ARM9 blob."""
    header_data = arm9_data[
        table_offset : table_offset + count * engine.MAP_HEADER_SIZE
    ]
    return engine.parse_map_headers(
        header_data, filesystem.read(map_names_path), count=count
    )


def resolve_map_headers(
    engine: Any,
    arm9_data: bytes,
    filesystem: Any,
    messages: Any,
    *,
    map_names_path: str,
    table_offset: int,
    count: int,
    location_names_member: int,
) -> tuple[tuple[Any, ...], tuple[str, ...]]:
    """Parse the map header table and resolve each header's location name.

    Shared by every extractor that joins headers with location names
    (encounters, trainers, locations) so the table parse and the "missing
    location name" validation happen exactly once instead of once per module.
    """
    headers = parse_map_header_table(
        engine,
        arm9_data,
        filesystem,
        map_names_path,
        table_offset=table_offset,
        count=count,
    )
    location_names = engine.parse_english_message_archive(
        messages.read(location_names_member)
    )
    for header in headers:
        if header.location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing location name "
                f"{header.location_name_id}"
            )
    return headers, location_names


@dataclass(frozen=True, slots=True)
class SegmentMapHeader:
    """One full map header from a Generation III `map_header_segments` run."""

    header_id: int
    rom_offset: int
    data: bytes
    name: str


def read_region_names(
    engine: Any, platform: Any, image: Any, *, offset: int, count: int
) -> list[str]:
    # `decode_gen3_text_sequence` scans for terminators starting at `offset`
    # within the given buffer, so the region-name table is read as one
    # oversized chunk (worst case, every entry uses its full padding budget)
    # rather than needing an exact byte length up front.
    data = platform.read_bytes(image, offset, count * 32)
    return engine.decode_gen3_text_sequence(data, offset=0, count=count)


def iter_segment_map_headers(
    engine: Any,
    platform: Any,
    image: Any,
    segments: Iterable[Iterable[int]],
    region_names: Sequence[str],
) -> Iterator[SegmentMapHeader]:
    """Yield each header of the profile's verified `map_header_segments` runs.

    Runs are concatenated in profile order, so `header_id` is the sequential
    synthetic ID the `locations` domain assigns to the same header.
    """
    header_size = engine.MAP_HEADER_SIZE
    header_id = 0
    for segment_offset, segment_count in segments:
        segment_data = platform.read_bytes(
            image, segment_offset, header_size * segment_count
        )
        for slot in range(segment_count):
            data = segment_data[slot * header_size : (slot + 1) * header_size]
            _music, _layout_id, region_id = engine.parse_map_header(
                data, header_id=header_id
            )
            yield SegmentMapHeader(
                header_id=header_id,
                rom_offset=segment_offset + slot * header_size,
                data=data,
                name=region_names[region_id],
            )
            header_id += 1
