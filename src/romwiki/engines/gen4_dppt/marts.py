from __future__ import annotations

from dataclasses import dataclass
import struct

from romwiki.errors import InvalidRomError
from romwiki.engines.gen4_dppt.scripts import _parse_script_table


COMMON_MART_COMMAND = 0x0147
SPECIALTY_MART_COMMAND = 0x0148
ITEM_RECORD_SIZE = 34
_CLOSE_MART_SEQUENCE = struct.pack("<HH", 0x0061, 0x0002)


@dataclass(frozen=True, slots=True)
class Gen4MartCommand:
    offset: int
    kind: str
    inventory_id: int


@dataclass(frozen=True, slots=True)
class Gen4CommonMartItem:
    item_id: int
    required_badges: int


def parse_mart_commands(data: bytes) -> tuple[Gen4MartCommand, ...]:
    code_offset = _parse_script_table(data)
    commands = []
    for offset in range(code_offset, len(data) - 7):
        opcode, inventory_id = struct.unpack_from("<HH", data, offset)
        if opcode not in {COMMON_MART_COMMAND, SPECIALTY_MART_COMMAND}:
            continue
        if data[offset + 4 : offset + 8] != _CLOSE_MART_SEQUENCE:
            continue
        commands.append(
            Gen4MartCommand(
                offset=offset,
                kind="common" if opcode == COMMON_MART_COMMAND else "specialty",
                inventory_id=inventory_id,
            )
        )
    return tuple(commands)


def parse_common_mart_inventory(
    data: bytes, *, offset: int, item_count: int
) -> tuple[Gen4CommonMartItem, ...]:
    items = []
    cursor = offset
    while cursor + 4 <= len(data):
        item_id, tier = struct.unpack_from("<HH", data, cursor)
        cursor += 4
        if item_id == 0 and tier == 0:
            return tuple(items)
        if not 0 < item_id < item_count:
            raise InvalidRomError(f"Common mart references invalid item {item_id}")
        if tier == 0:
            raise InvalidRomError("Common mart item has an invalid progression tier")
        items.append(
            Gen4CommonMartItem(item_id=item_id, required_badges=tier - 1)
        )
    raise InvalidRomError("Common mart inventory is unterminated")


def parse_specialty_mart_inventories(
    data: bytes,
    *,
    pointer_table_offset: int,
    inventory_count: int,
    load_address: int,
    item_count: int,
) -> tuple[tuple[int, ...], ...]:
    table_end = pointer_table_offset + inventory_count * 4
    if pointer_table_offset < 0 or table_end > len(data):
        raise InvalidRomError("Specialty mart pointer table is out of bounds")

    inventories = []
    for index in range(inventory_count):
        pointer = struct.unpack_from("<I", data, pointer_table_offset + index * 4)[0]
        cursor = pointer - load_address
        if not 0 <= cursor < len(data):
            raise InvalidRomError(
                f"Specialty mart {index} inventory pointer is out of bounds"
            )
        items = []
        while cursor + 2 <= len(data):
            item_id = struct.unpack_from("<H", data, cursor)[0]
            cursor += 2
            if item_id == 0xFFFF:
                break
            if not 0 < item_id < item_count:
                raise InvalidRomError(
                    f"Specialty mart {index} references invalid item {item_id}"
                )
            items.append(item_id)
        else:
            raise InvalidRomError(f"Specialty mart {index} inventory is unterminated")
        inventories.append(tuple(items))
    return tuple(inventories)


def parse_item_price(data: bytes) -> int:
    if len(data) != ITEM_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV item record must be {ITEM_RECORD_SIZE} bytes, got {len(data)}"
        )
    return struct.unpack_from("<H", data)[0]
