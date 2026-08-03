from __future__ import annotations

from romwiki.engines.gen5.locations import (
    parse_map_header_script_files as parse_map_header_script_files,
)
from romwiki.engines.gen5.locations import (
    parse_map_header_table as _parse_map_header_table,
)
from romwiki.engines.gen5.locations import (
    parse_map_header_text_files as parse_map_header_text_files,
)
from romwiki.engines.gen5.locations import (
    parse_wild_map_names as _parse_wild_map_names,
)
from romwiki.schema import EncounterMapLocation

# B2W2 packs flags into the high nibble of BW's 16-bit wild-set field.
# The low twelve bits cover every encounter archive index; 0xFFF is null
# regardless of the flag combination.
_WILD_SET_MASK = 0x0FFF
WARP_DESTINATION_INDEXED = False
COMMON_SCRIPT_MEMBER_BASE = 808

# The sequels' fixed NPC trades are invoked by shared trade code, while the
# caller's map owns the person text. The first 24 records are Curtis/Yancy
# phone trades and deliberately have no single map.
NPC_TRADE_TEXT_MEMBER_BY_ID = {
    24: 529,
    25: 529,
    26: 555,
    27: 193,
    28: 594,
    29: 628,
    30: 628,
}


def resolve_common_script_member(
    script_used: int, *, member_count: int
) -> int | None:
    if script_used < 10000:
        return None
    member = COMMON_SCRIPT_MEMBER_BASE + script_used - 10000
    return member if member < member_count else None


def parse_map_header_table(
    data: bytes, *, map_names: tuple[str, ...], archive_path: str
) -> tuple[EncounterMapLocation, ...]:
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
