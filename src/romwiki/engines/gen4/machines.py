from __future__ import annotations

import struct

from romwiki.engines.gen4.constants import MAX_MOVE_ID
from romwiki.schema import Machine
from romwiki.util.errors import InvalidRomError

GEN4_MACHINE_COUNT = 100
GEN4_TM_COUNT = 92
_GEN4_MACHINE_ITEM_ID_OFFSET = 327


def machine_name(machine_id: int) -> str:
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
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen IV machine {index + 1} has invalid move ID {move_id}"
            )
        kind = "tm" if index < tm_count else "hm"
        number = index + 1 if index < tm_count else index - tm_count + 1
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
