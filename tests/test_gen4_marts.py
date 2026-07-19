from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import (
    ITEM_RECORD_SIZE,
    parse_common_mart_inventory,
    parse_item_price,
    parse_mart_commands,
    parse_specialty_mart_inventories,
)
from romwiki.errors import InvalidRomError


def make_script(body: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + body


class Gen4MartTests(unittest.TestCase):
    def test_extracts_common_and_specialty_mart_commands(self) -> None:
        body = (
            struct.pack("<HHHH", 0x0147, 1, 0x0061, 0x0002)
            + struct.pack("<HHHH", 0x0148, 16, 0x0061, 0x0002)
        )

        commands = parse_mart_commands(make_script(body))

        self.assertEqual(
            [(command.offset, command.kind, command.inventory_id) for command in commands],
            [(6, "common", 1), (14, "specialty", 16)],
        )

    def test_ignores_unverified_mart_opcode_values(self) -> None:
        body = struct.pack("<HHHH", 0x0148, 16, 0x0028, 0x8004)
        self.assertEqual(parse_mart_commands(make_script(body)), ())

    def test_parses_common_mart_badge_requirements(self) -> None:
        data = b"padding" + struct.pack("<HHHHHH", 4, 1, 3, 3, 0, 0)

        items = parse_common_mart_inventory(data, offset=7, item_count=500)

        self.assertEqual(
            [(item.item_id, item.required_badges) for item in items],
            [(4, 0), (3, 2)],
        )

    def test_parses_pointer_based_specialty_inventories(self) -> None:
        load_address = 0x02000000
        data = bytearray(40)
        struct.pack_into("<II", data, 0, load_address + 16, load_address + 24)
        struct.pack_into("<HHH", data, 16, 59, 57, 0xFFFF)
        struct.pack_into("<HH", data, 24, 146, 0xFFFF)

        inventories = parse_specialty_mart_inventories(
            bytes(data),
            pointer_table_offset=0,
            inventory_count=2,
            load_address=load_address,
            item_count=500,
        )

        self.assertEqual(inventories, ((59, 57), (146,)))

    def test_rejects_invalid_specialty_item(self) -> None:
        data = struct.pack("<IHH", 8, 500, 0xFFFF)
        with self.assertRaises(InvalidRomError):
            parse_specialty_mart_inventories(
                data,
                pointer_table_offset=0,
                inventory_count=1,
                load_address=0,
                item_count=500,
            )

    def test_reads_item_price(self) -> None:
        record = struct.pack("<H", 1200) + bytes(ITEM_RECORD_SIZE - 2)
        self.assertEqual(parse_item_price(record), 1200)


if __name__ == "__main__":
    unittest.main()
