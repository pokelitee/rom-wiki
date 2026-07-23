"""Shared ARM9 and map-header table reading, used by every extractor that
resolves in-game location names (encounters, trainers, locations, tutors).
"""

from __future__ import annotations

from typing import Any


def read_arm9(image: Any) -> bytes:
    """Read the full ARM9 binary blob from a ROM image."""
    with image.path.open("rb") as stream:
        stream.seek(image.header.arm9_offset)
        return stream.read(image.header.arm9_size)


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
    return engine.parse_platinum_map_headers(
        header_data, filesystem.read(map_names_path), count=count
    )
