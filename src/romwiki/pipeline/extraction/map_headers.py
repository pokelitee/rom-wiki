"""Shared code-binary and map-header table reading, used by every extractor
that resolves in-game location names (encounters, trainers, locations, tutors).
"""

from __future__ import annotations

from typing import Any

from romwiki.util.errors import DataSourceError, InvalidRomError


def read_code_binary(platform: Any, image: Any, engine: Any | None = None) -> bytes:
    """Read the platform's main code binary (the ARM9 blob on Nintendo DS)."""
    if engine is not None and getattr(engine, "CODE_BINARY_DECOMPRESSED", False):
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
