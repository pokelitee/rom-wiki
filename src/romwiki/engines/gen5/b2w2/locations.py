from __future__ import annotations

from romwiki.engines.gen5.locations import (
    parse_map_header_script_files as _parse_map_header_script_files,
)
from romwiki.engines.gen5.locations import (
    parse_map_header_table as _parse_map_header_table,
)
from romwiki.engines.gen5.locations import (
    parse_wild_map_names as _parse_wild_map_names,
)
from romwiki.schema import Gen5Location

# B2W2 packs flags into the high nibble of BW's 16-bit wild-set field.
# The low twelve bits cover every encounter archive index; 0xFFF is null
# regardless of the flag combination.
_WILD_SET_MASK = 0x0FFF


def parse_map_header_script_files(data: bytes) -> tuple[int, ...]:
    return _parse_map_header_script_files(data)


def parse_map_header_table(
    data: bytes, *, map_names: tuple[str, ...], archive_path: str
) -> tuple[Gen5Location, ...]:
    return _parse_map_header_table(
        data,
        map_names=map_names,
        archive_path=archive_path,
        wild_set_mask=_WILD_SET_MASK,
    )


def parse_wild_map_names(
    data: bytes, *, map_names: tuple[str, ...]
) -> dict[int, list[str]]:
    return _parse_wild_map_names(
        data,
        map_names=map_names,
        wild_set_mask=_WILD_SET_MASK,
    )
