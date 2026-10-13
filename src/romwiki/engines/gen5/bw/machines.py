from __future__ import annotations

import struct

from romwiki.engines.gen5.shared.machines import (
    machine_id_for_table_index as machine_id_for_table_index,
)
from romwiki.schema import Machine
from romwiki.util.errors import InvalidRomError

from .constants import (
    GEN5_HM_COUNT,
    GEN5_HM_ITEM_ID_OFFSET,
    GEN5_MACHINE_COUNT,
    GEN5_TM_BLOCK_ONE_COUNT,
    GEN5_TM_BLOCK_ONE_ITEM_ID_OFFSET,
    GEN5_TM_BLOCK_TWO_ITEM_ID_BASE,
    GEN5_TM_COUNT,
    MAX_MOVE_ID,
)

_BLOCK_TWO_START = GEN5_TM_BLOCK_ONE_COUNT + GEN5_HM_COUNT


def machine_name(machine_id: int) -> str:
    if machine_id <= GEN5_TM_COUNT:
        return f"TM{machine_id:02}"
    if machine_id <= GEN5_MACHINE_COUNT:
        return f"HM{machine_id - GEN5_TM_COUNT:02}"
    return f"MACHINE{machine_id:03}"


def parse_machine_move_table(data: bytes) -> tuple[Machine, ...]:
    expected_size = GEN5_MACHINE_COUNT * 2
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen V machine table has size {len(data)}, expected {expected_size}"
        )

    machines = []
    for index, (move_id,) in enumerate(struct.iter_unpack("<H", data)):
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen V machine {index + 1} has invalid move ID {move_id}"
            )
        machine_id = machine_id_for_table_index(index)
        if index < GEN5_TM_BLOCK_ONE_COUNT:
            kind = "tm"
            number = index + 1
            item_id = GEN5_TM_BLOCK_ONE_ITEM_ID_OFFSET + number
        elif index < _BLOCK_TWO_START:
            kind = "hm"
            number = index - GEN5_TM_BLOCK_ONE_COUNT + 1
            item_id = GEN5_HM_ITEM_ID_OFFSET + number
        else:
            kind = "tm"
            number = GEN5_TM_BLOCK_ONE_COUNT + (index - _BLOCK_TWO_START) + 1
            item_id = GEN5_TM_BLOCK_TWO_ITEM_ID_BASE + (
                number - (GEN5_TM_BLOCK_ONE_COUNT + 1)
            )
        machines.append(
            Machine(
                machine_id=machine_id,
                kind=kind,
                number=number,
                move_id=move_id,
                table_index=index,
                item_id=item_id,
            )
        )
    return tuple(sorted(machines, key=lambda machine: machine.machine_id))
