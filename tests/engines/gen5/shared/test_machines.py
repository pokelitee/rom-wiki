from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.machines import (
    machine_id_for_table_index,
    machine_name,
    parse_machine_move_table,
)
from romwiki.util.errors import InvalidRomError


class Gen5MachineTests(unittest.TestCase):
    def test_names_tms(self) -> None:
        self.assertEqual(machine_name(1), "TM01")
        self.assertEqual(machine_name(92), "TM92")
        self.assertEqual(machine_name(93), "TM93")
        self.assertEqual(machine_name(95), "TM95")

    def test_names_hms(self) -> None:
        self.assertEqual(machine_name(96), "HM01")
        self.assertEqual(machine_name(101), "HM06")

    def test_falls_back_beyond_known_range(self) -> None:
        self.assertEqual(machine_name(102), "MACHINE102")

    def test_maps_physical_table_position_to_published_machine_id(self) -> None:
        # Physical ARM9 move-table order: TM01-92 (index 0-91), HM01-06
        # (index 92-97), TM93-95 (index 98-100).
        self.assertEqual(machine_id_for_table_index(0), 1)  # TM01
        self.assertEqual(machine_id_for_table_index(91), 92)  # TM92
        self.assertEqual(machine_id_for_table_index(92), 96)  # HM01
        self.assertEqual(machine_id_for_table_index(97), 101)  # HM06
        self.assertEqual(machine_id_for_table_index(98), 93)  # TM93
        self.assertEqual(machine_id_for_table_index(100), 95)  # TM95

    def test_parses_the_three_table_blocks(self) -> None:
        # Real Black ROM values: TM01=Hone Claws (468), TM92=Trick Room (433),
        # HM01=Cut (15), HM06=Dive (291), TM93=Wild Charge (528),
        # TM95=Snarl (555).
        move_ids = [468] + [1] * 90 + [433] + [15, 1, 1, 1, 1, 291] + [528, 1, 555]
        data = struct.pack(f"<{len(move_ids)}H", *move_ids)

        machines = parse_machine_move_table(data)

        self.assertEqual(len(machines), 101)
        self.assertEqual(
            tuple(machine.machine_id for machine in machines), tuple(range(1, 102))
        )
        self.assertEqual(
            (
                machines[0].kind,
                machines[0].number,
                machines[0].move_id,
                machines[0].item_id,
            ),
            ("tm", 1, 468, 328),
        )
        self.assertEqual(
            (
                machines[91].kind,
                machines[91].number,
                machines[91].move_id,
                machines[91].item_id,
            ),
            ("tm", 92, 433, 419),
        )
        self.assertEqual(
            (
                machines[92].kind,
                machines[92].number,
                machines[92].move_id,
                machines[92].table_index,
                machines[92].item_id,
            ),
            ("tm", 93, 528, 98, 618),
        )
        self.assertEqual(
            (
                machines[94].kind,
                machines[94].number,
                machines[94].move_id,
                machines[94].table_index,
                machines[94].item_id,
            ),
            ("tm", 95, 555, 100, 620),
        )
        self.assertEqual(
            (
                machines[95].kind,
                machines[95].number,
                machines[95].move_id,
                machines[95].table_index,
                machines[95].item_id,
            ),
            ("hm", 1, 15, 92, 420),
        )
        self.assertEqual(
            (
                machines[100].kind,
                machines[100].number,
                machines[100].move_id,
                machines[100].table_index,
                machines[100].item_id,
            ),
            ("hm", 6, 291, 97, 425),
        )

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_machine_move_table(b"short")

    def test_rejects_invalid_move_id(self) -> None:
        move_ids = [0] * 101
        with self.assertRaises(InvalidRomError):
            parse_machine_move_table(struct.pack("<101H", *move_ids))


if __name__ == "__main__":
    unittest.main()
