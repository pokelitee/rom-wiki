from __future__ import annotations

from romwiki.util.errors import InvalidRomError

# GBA ROM addresses are mapped starting at 0x08000000 (the cartridge ROM
# address space in the GBA's memory map) through 0x0A000000 (32MB, the
# largest possible GBA cartridge). Shared by every Generation III struct
# that stores a pointer to another ROM location -- first needed by the
# trainer party pointer (`trainers.py`), now also by the wild-encounter
# header's per-method pointers and each method's own slots pointer
# (`encounters.py`).
_ROM_BASE = 0x08000000
_ROM_END = 0x0A000000


def resolve_gba_pointer(value: int) -> int:
    """Convert a raw GBA ROM address (0x08000000-based) to a file offset."""
    if not _ROM_BASE <= value < _ROM_END:
        raise InvalidRomError(
            f"Value is not a valid Game Boy Advance pointer: {value:#x}"
        )
    return value - _ROM_BASE


def gba_pointer_for_offset(offset: int) -> int:
    """Convert a file offset to the raw GBA ROM address (0x08000000-based)
    that would point to it -- the inverse of `resolve_gba_pointer`, needed
    when comparing/constructing pointer values rather than resolving one
    already read from ROM data (e.g. `encounters.py`'s wild-encounter-to-
    location backfill, matching pointer values found in `gMapGroups`
    against file offsets computed from `map_header_segments`).
    """
    return offset + _ROM_BASE
