"""Shared code-binary and map-header table reading, used by every extractor
that resolves in-game location names (encounters, trainers, locations, tutors).
"""

from __future__ import annotations

from collections.abc import Iterator
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
class GbaMapHeader:
    """One Generation III `MapHeader`, reached through `gMapGroups`."""

    header_id: int
    map_group: int
    map_num: int
    rom_offset: int
    data: bytes
    name: str


def iter_gba_map_headers(
    engine: Any, platform: Any, image: Any, profile: Any
) -> Iterator[GbaMapHeader]:
    """Yield every named map in `gMapGroups`, in (group, number) order.

    `header_id` numbers all maps in that order; it is the synthetic ID the
    `locations` domain and every location backfill share. Maps in a section
    whose name is empty are skipped: Emerald's dynamic section (the S.S.
    Tidal's cabins, for example) shows wherever the player came from, so
    the ROM gives those maps no name of their own.
    """
    gmapgroups_offset = profile.int_parameter("gmapgroups_offset")
    group_count = profile.int_parameter(
        "map_group_count", engine.GMAPGROUPS_GROUP_COUNT
    )
    group_pointers = engine.parse_gmapgroups_pointers(
        platform.read_bytes(image, gmapgroups_offset, group_count * 4),
        group_count=group_count,
    )
    addresses = engine.parse_map_group_index(
        group_pointers,
        lambda offset, size: platform.read_bytes(image, offset, size),
        gmapgroups_address=engine.gba_pointer_for_offset(gmapgroups_offset),
    )
    region_names = read_region_names(engine, platform, image, profile)
    header_size = engine.MAP_HEADER_SIZE
    for header_id, ((group, num), address) in enumerate(sorted(addresses.items())):
        offset = engine.resolve_gba_pointer(address)
        data = platform.read_bytes(image, offset, header_size)
        _music, _layout_id, section = engine.parse_map_header(data, header_id=header_id)
        if section not in region_names:
            raise InvalidRomError(
                f"Gen III map {group}.{num} has unknown region map section {section}"
            )
        if not region_names[section]:
            continue
        yield GbaMapHeader(
            header_id=header_id,
            map_group=group,
            map_num=num,
            rom_offset=offset,
            data=data,
            name=region_names[section],
        )


def read_region_names(
    engine: Any, platform: Any, image: Any, profile: Any
) -> dict[int, str]:
    """Map each region map section to its Town Map name.

    The profile's table holds one name pointer per section, starting at the
    engine's first section: FireRed/LeafGreen's `sMapNames` covers only
    Kanto's sections, while Emerald's `gRegionMapEntries` covers every one.
    Several sections may share one name string.
    """
    offset = profile.int_parameter("region_name_offset")
    count = profile.int_parameter("region_name_count")
    entry_size = engine.REGION_NAME_ENTRY_SIZE
    table = platform.read_bytes(image, offset, count * entry_size)
    names = {}
    for index in range(count):
        pointer_at = index * entry_size + engine.REGION_NAME_POINTER_OFFSET
        pointer = int.from_bytes(table[pointer_at : pointer_at + 4], "little")
        names[engine.FIRST_REGION_MAP_SECTION + index] = engine.decode_gen3_name(
            platform.read_bytes(
                image, engine.resolve_gba_pointer(pointer), _REGION_NAME_READ_SIZE
            )
        )
    return names


# Bytes read per region name; the longest retail name is 16 characters, and
# decoding stops at the terminator.
_REGION_NAME_READ_SIZE = 32
