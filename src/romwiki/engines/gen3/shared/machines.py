from __future__ import annotations

import struct

from romwiki.engines.gen3.shared.constants import (
    FIRST_MACHINE_ITEM_ID,
    MACHINE_COUNT,
    MAX_MOVE_ID,
    TM_COUNT,
)
from romwiki.schema import Machine
from romwiki.util.errors import InvalidRomError


def machine_name(machine_id: int) -> str:
    if machine_id <= TM_COUNT:
        return f"TM{machine_id:02}"
    if machine_id <= MACHINE_COUNT:
        return f"HM{machine_id - TM_COUNT:02}"
    return f"MACHINE{machine_id:03}"


def parse_machine_move_table(
    data: bytes,
    *,
    machine_count: int = MACHINE_COUNT,
    tm_count: int = TM_COUNT,
) -> tuple[Machine, ...]:
    if machine_count <= 0 or not 0 <= tm_count <= machine_count:
        raise InvalidRomError("Gen III machine table configuration is invalid")
    expected_size = machine_count * 2
    if len(data) != expected_size:
        raise InvalidRomError(
            f"Gen III machine table has size {len(data)}, expected {expected_size}"
        )
    machines = []
    for index, (move_id,) in enumerate(struct.iter_unpack("<H", data)):
        if not 1 <= move_id <= MAX_MOVE_ID:
            raise InvalidRomError(
                f"Gen III machine {index + 1} has invalid move ID {move_id}"
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
                item_id=index + FIRST_MACHINE_ITEM_ID,
            )
        )
    return tuple(machines)


def parse_tmhm_learnset(data: bytes) -> tuple[int, tuple[int, int, int, int]]:
    """Decode an 8-byte `sTMHMLearnsets` entry into `(bits, machine_masks)`
    -- the raw 64-bit compatibility bitmask, and the same value split into
    the `PokemonPersonalData.machine_masks` four-u32 shape every other
    engine's inline bitmap already produces (the top two u32s always zero,
    since Generation III only has 58 machines).
    """
    if len(data) != 8:
        raise InvalidRomError(
            f"Gen III TM/HM learnset entry has size {len(data)}, expected 8"
        )
    low, high = struct.unpack("<II", data)
    bits = low | (high << 32)
    return bits, (low, high, 0, 0)
