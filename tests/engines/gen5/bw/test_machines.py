from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.bw.machines import machine_name, parse_machine_move_table
from romwiki.util.errors import InvalidRomError


class Gen5MachineTests(unittest.TestCase):
    def test_names_tm_block_one(self) -> None:
        self.assertEqual(machine_name(1), "TM01")
        self.assertEqual(machine_name(92), "TM92")

    def test_names_hms(self) -> None:
        self.assertEqual(machine_name(93), "HM01")
        self.assertEqual(machine_name(98), "HM06")

    def test_names_tm_block_two(self) -> None:
        # The real ARM9 table interleaves a final TM93-95 block after the
        # HMs, unlike Generation IV's simple contiguous TM-then-HM layout.
        self.assertEqual(machine_name(99), "TM93")
        self.assertEqual(machine_name(101), "TM95")

    def test_falls_back_beyond_known_range(self) -> None:
        self.assertEqual(machine_name(102), "MACHINE102")

    def test_parses_the_three_table_blocks(self) -> None:
        # Real Black ROM values: TM01=Hone Claws (468), TM92=Trick Room (433),
        # HM01=Cut (15), HM06=Dive (291), TM93=Wild Charge (528),
        # TM95=Snarl (555).
        move_ids = [468] + [1] * 90 + [433] + [15, 1, 1, 1, 1, 291] + [528, 1, 555]
        data = struct.pack(f"<{len(move_ids)}H", *move_ids)

        machines = parse_machine_move_table(data)

        self.assertEqual(len(machines), 101)
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
                machines[92].item_id,
            ),
            ("hm", 1, 15, 420),
        )
        self.assertEqual(
            (
                machines[97].kind,
                machines[97].number,
                machines[97].move_id,
                machines[97].item_id,
            ),
            ("hm", 6, 291, 425),
        )
        self.assertEqual(
            (
                machines[98].kind,
                machines[98].number,
                machines[98].move_id,
                machines[98].item_id,
            ),
            ("tm", 93, 528, 618),
        )
        self.assertEqual(
            (
                machines[100].kind,
                machines[100].number,
                machines[100].move_id,
                machines[100].item_id,
            ),
            ("tm", 95, 555, 620),
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
