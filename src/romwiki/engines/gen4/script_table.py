"""Generation IV's field-script table header, shared by both engine leaves.

Platinum and HeartGold/SoulSilver use the same layout: a run of signed
relative offsets, each measured from the end of its own field, ending either
at a terminator or at the first script it points to.
"""

from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError

SCRIPT_TABLE_END = 0xFD13

#: Upper bound (exclusive) on this generation's script opcode space, used by
#: both engine leaves to sanity-check a "does this look like a real
#: follow-on opcode" heuristic during byte-pattern script scanning.
SCRIPT_COMMAND_COUNT = 0x033A


def parse_script_table(data: bytes) -> int:
    cursor = 0
    targets = []
    table_end = len(data)
    terminated = False
    while cursor < table_end:
        if cursor + 2 > len(data):
            raise InvalidRomError("Gen IV script table is truncated")
        if struct.unpack_from("<H", data, cursor)[0] == SCRIPT_TABLE_END:
            terminated = True
            break
        if cursor + 4 > table_end:
            raise InvalidRomError("Gen IV script table is truncated")
        relative_offset = struct.unpack_from("<i", data, cursor)[0]
        target = cursor + 4 + relative_offset
        targets.append(target)
        table_end = min(table_end, target)
        cursor += 4

    if not targets:
        raise InvalidRomError("Gen IV script table has no entries")
    if not terminated and cursor != table_end:
        raise InvalidRomError("Gen IV script table does not end at its first script")
    if any(target < table_end or target >= len(data) for target in targets):
        raise InvalidRomError("Gen IV script table contains an invalid entry offset")
    return table_end
