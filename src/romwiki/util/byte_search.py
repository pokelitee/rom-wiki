from __future__ import annotations

from romwiki.util.errors import InvalidRomError


def find_unique_pattern(data: bytes, pattern: bytes, *, label: str) -> int:
    """Find `pattern`'s one-and-only occurrence in `data`, or raise.

    Used wherever this generation's data has no stable absolute offset across
    ROM builds (e.g. a BLZ-compressed ARM9/overlay), unlike Generation IV's
    fixed file offsets -- raises rather than silently taking the first match
    if the pattern isn't unique, since a non-unique hit means the pattern
    needs to be more specific, not that the first one is correct.
    """
    first = data.find(pattern)
    if first == -1:
        raise InvalidRomError(f"Could not locate {label}")
    if data.find(pattern, first + 1) != -1:
        raise InvalidRomError(f"{label} byte pattern is not unique")
    return first
