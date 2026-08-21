from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.shared.machines import parse_machine_move_table
from romwiki.util.errors import InvalidRomError


class Gen4MachineTests(unittest.TestCase):
    def test_decodes_tm_and_hm_assignments(self) -> None:
        move_ids = tuple(range(1, 101))

        machines = parse_machine_move_table(struct.pack("<100H", *move_ids))

        self.assertEqual(machines[0].name, "TM01")
        self.assertEqual(machines[0].move_id, 1)
        self.assertEqual(machines[91].name, "TM92")
        self.assertEqual(machines[92].name, "HM01")
        self.assertEqual(machines[99].name, "HM08")
        self.assertEqual(machines[99].table_index, 99)

    def test_rejects_wrong_size_or_invalid_move_id(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_machine_move_table(b"short")
        data = bytearray(struct.pack("<100H", *range(1, 101)))
        struct.pack_into("<H", data, 0, 0)
        with self.assertRaises(InvalidRomError):
            parse_machine_move_table(bytes(data))

    def test_supports_profile_defined_table_dimensions(self) -> None:
        machines = parse_machine_move_table(
            struct.pack("<3H", 10, 20, 30), machine_count=3, tm_count=2
        )
        self.assertEqual(
            [machine.name for machine in machines], ["TM01", "TM02", "HM01"]
        )


if __name__ == "__main__":
    unittest.main()
