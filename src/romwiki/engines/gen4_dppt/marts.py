from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4_dppt.items import GEN4_ITEM_RECORD_SIZE
from romwiki.engines.gen4_dppt.scripts import parse_script_table
from romwiki.util.errors import InvalidRomError

COMMON_MART_COMMAND = 0x0147
SPECIALTY_MART_COMMAND = 0x0148
DECORATION_MART_COMMAND = 0x0149
SEAL_MART_COMMAND = 0x014A
FRONTIER_MART_COMMAND = 0x02D8
ITEM_RECORD_SIZE = GEN4_ITEM_RECORD_SIZE
DECORATION_RECORD_SIZE = 28
SEAL_RECORD_SIZE = 10
_CLOSE_MART_SEQUENCE = struct.pack("<HH", 0x0061, 0x0002)
_CLOSE_SEAL_MART_COMMAND = struct.pack("<H", 0x001B)
_MART_KINDS = {
    COMMON_MART_COMMAND: "common",
    SPECIALTY_MART_COMMAND: "specialty",
    DECORATION_MART_COMMAND: "decoration",
    SEAL_MART_COMMAND: "seal",
    FRONTIER_MART_COMMAND: "frontier",
}


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
    code_offset = parse_script_table(data)
    commands = []
    for offset in range(code_offset, len(data) - 3):
        opcode = struct.unpack_from("<H", data, offset)[0]
        if opcode not in _MART_KINDS:
            continue
        if opcode == FRONTIER_MART_COMMAND:
            inventory_id = data[offset + 2]
            suffix_offset = offset + 3
            expected_suffix = _CLOSE_MART_SEQUENCE
        else:
            inventory_id = struct.unpack_from("<H", data, offset + 2)[0]
            suffix_offset = offset + 4
            expected_suffix = (
                _CLOSE_SEAL_MART_COMMAND
                if opcode == SEAL_MART_COMMAND
                else _CLOSE_MART_SEQUENCE
            )
        if data[suffix_offset : suffix_offset + len(expected_suffix)] != expected_suffix:
            continue
        commands.append(
            Gen4MartCommand(
                offset=offset,
                kind=_MART_KINDS[opcode],
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


def parse_decoration_price_table(
    data: bytes, *, offset: int, decoration_count: int
) -> tuple[int, ...]:
    return _parse_price_table(
        data,
        offset=offset,
        record_size=DECORATION_RECORD_SIZE,
        count=decoration_count,
        price_format="<I",
        catalog_name="Decoration",
    )


def parse_seal_price_table(
    data: bytes, *, offset: int, seal_count: int
) -> tuple[int, ...]:
    return _parse_price_table(
        data,
        offset=offset,
        record_size=SEAL_RECORD_SIZE,
        count=seal_count,
        price_format="<H",
        catalog_name="Seal",
    )


def parse_frontier_price_table(
    data: bytes, *, offset: int, record_count: int
) -> dict[int, int]:
    table_end = offset + record_count * 4
    if offset < 0 or record_count < 0 or table_end > len(data):
        raise InvalidRomError("Battle Frontier price table is out of bounds")
    prices = {}
    for index in range(record_count):
        item_id, price = struct.unpack_from("<HH", data, offset + index * 4)
        if item_id in prices:
            raise InvalidRomError(
                f"Battle Frontier price table repeats item {item_id}"
            )
        prices[item_id] = price
    return prices


def _parse_price_table(
    data: bytes,
    *,
    offset: int,
    record_size: int,
    count: int,
    price_format: str,
    catalog_name: str,
) -> tuple[int, ...]:
    table_end = offset + record_size * count
    if offset < 0 or count < 0 or table_end > len(data):
        raise InvalidRomError(f"{catalog_name} price table is out of bounds")
    return tuple(
        struct.unpack_from(price_format, data, offset + index * record_size)[0]
        for index in range(count)
    )
