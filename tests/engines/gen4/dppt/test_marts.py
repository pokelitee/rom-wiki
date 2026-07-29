from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import (
    ITEM_RECORD_SIZE,
    parse_common_mart_inventory,
    parse_decoration_price_table,
    parse_frontier_price_table,
    parse_item_price,
    parse_mart_commands,
    parse_seal_price_table,
    parse_specialty_mart_inventories,
)
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script


class Gen4MartTests(unittest.TestCase):
    def test_extracts_supported_mart_commands(self) -> None:
        body = (
            struct.pack("<HHHH", 0x0147, 1, 0x0061, 0x0002)
            + struct.pack("<HHHH", 0x0148, 16, 0x0061, 0x0002)
            + struct.pack("<HHHH", 0x0149, 1, 0x0061, 0x0002)
            + struct.pack("<HHH", 0x014A, 6, 0x001B)
            + struct.pack("<HBHH", 0x02D8, 1, 0x0061, 0x0002)
        )

        commands = parse_mart_commands(make_script(body))

        self.assertEqual(
            [
                (command.offset, command.kind, command.inventory_id)
                for command in commands
            ],
            [
                (6, "common", 1),
                (14, "specialty", 16),
                (22, "decoration", 1),
                (30, "seal", 6),
                (36, "frontier", 1),
            ],
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

    def test_reads_decoration_prices_from_fixed_size_records(self) -> None:
        data = bytearray(8 + 2 * 28)
        struct.pack_into("<I", data, 8, 500)
        struct.pack_into("<I", data, 8 + 28, 3000)

        self.assertEqual(
            parse_decoration_price_table(data, offset=8, decoration_count=2),
            (500, 3000),
        )

    def test_reads_seal_prices_from_fixed_size_records(self) -> None:
        data = bytearray(4 + 3 * 10)
        struct.pack_into("<H", data, 4, 50)
        struct.pack_into("<H", data, 14, 100)
        struct.pack_into("<H", data, 24, 150)

        self.assertEqual(
            parse_seal_price_table(data, offset=4, seal_count=3),
            (50, 100, 150),
        )

    def test_rejects_truncated_specialized_price_table(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_decoration_price_table(bytes(28), offset=0, decoration_count=2)

    def test_reads_battle_frontier_item_price_records(self) -> None:
        data = struct.pack("<HHHH", 289, 16, 333, 32)

        self.assertEqual(
            parse_frontier_price_table(data, offset=0, record_count=2),
            {289: 16, 333: 32},
        )


if __name__ == "__main__":
    unittest.main()
