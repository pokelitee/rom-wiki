"""Shared code-binary and map-header table reading, used by every extractor
that resolves in-game location names (encounters, trainers, locations, tutors).
"""

from __future__ import annotations

from typing import Any

from romwiki.util.errors import DataSourceError


def read_code_binary(platform: Any, image: Any) -> bytes:
    """Read the platform's main code binary (the ARM9 blob on Nintendo DS)."""
    if platform.read_code_binary is None:
        raise DataSourceError(
            "The selected platform does not expose a code binary"
        )
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
