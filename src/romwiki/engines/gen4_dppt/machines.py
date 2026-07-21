from __future__ import annotations

import struct

from romwiki.util.errors import InvalidRomError
from romwiki.schema import Gen4Machine


GEN4_MACHINE_COUNT = 100
GEN4_TM_COUNT = 92


def parse_machine_move_table(
    data: bytes,
    *,
    machine_count: int = GEN4_MACHINE_COUNT,
    tm_count: int = GEN4_TM_COUNT,
) -> tuple[Gen4Machine, ...]:
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
            Gen4Machine(
                machine_id=index + 1,
                kind=kind,
                number=number,
                move_id=move_id,
                table_index=index,
            )
        )
    return tuple(machines)
