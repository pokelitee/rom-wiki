from __future__ import annotations

import struct

from romwiki.schema import Machine
from romwiki.util.errors import InvalidRomError

GEN4_MACHINE_COUNT = 100
GEN4_TM_COUNT = 92
# TM01-TM92 and HM01-HM08 occupy a fixed, contiguous block of item IDs
# (328-427) in every Gen IV game, in the same order as `machine_id`. This
# layout is engine data, not ROM-hack-mutable, so it's derived rather than
# read per-ROM.
_GEN4_MACHINE_ITEM_ID_OFFSET = 327


def machine_name(machine_id: int) -> str:
    """Format a machine ID the way `Machine.name` would."""
    if machine_id <= GEN4_TM_COUNT:
        return f"TM{machine_id:02}"
    if machine_id <= GEN4_MACHINE_COUNT:
        return f"HM{machine_id - GEN4_TM_COUNT:02}"
    return f"MACHINE{machine_id:03}"


def parse_machine_move_table(
    data: bytes,
    *,
    machine_count: int = GEN4_MACHINE_COUNT,
    tm_count: int = GEN4_TM_COUNT,
) -> tuple[Machine, ...]:
    if machine_count <= 0 or not 0 <= tm_count <= machine_count:
        raise InvalidRomError("Gen IV machine table configuration is invalid")
    expected_size = machine_count * 2
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen IV machine table has size {len(data)}, expected {expected_size}"
        )

    machines = []
    for index, (move_id,) in enumerate(struct.iter_unpack("<H", data)):
        if not 1 <= move_id <= 467:
            raise InvalidRomError(
                f"Gen IV machine {index + 1} has invalid move ID {move_id}"
            )
        if index < tm_count:
            kind = "tm"
            number = index + 1
        else:
            kind = "hm"
            number = index - tm_count + 1
        machines.append(
            Machine(
                machine_id=index + 1,
                kind=kind,
                number=number,
                move_id=move_id,
                table_index=index,
                item_id=index + 1 + _GEN4_MACHINE_ITEM_ID_OFFSET,
            )
        )
    return tuple(machines)
