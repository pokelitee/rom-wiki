from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.machines import (
    machine_name,
    parse_machine_move_table,
    parse_tmhm_learnset,
)
from romwiki.util.errors import InvalidRomError


class MachineNameTests(unittest.TestCase):
    def test_names_tms_hms_and_out_of_range_values(self) -> None:
        self.assertEqual(machine_name(1), "TM01")
        self.assertEqual(machine_name(50), "TM50")
        self.assertEqual(machine_name(51), "HM01")
        self.assertEqual(machine_name(58), "HM08")
        self.assertEqual(machine_name(59), "MACHINE059")


class ParseMachineMoveTableTests(unittest.TestCase):
    def test_decodes_tm_and_hm_assignments(self) -> None:
        move_ids = tuple(range(1, 59))

        machines = parse_machine_move_table(struct.pack("<58H", *move_ids))

        self.assertEqual(machines[0].name, "TM01")
        self.assertEqual(machines[0].move_id, 1)
        self.assertEqual(machines[0].item_id, 289)
        self.assertEqual(machines[49].name, "TM50")
        self.assertEqual(machines[50].name, "HM01")
        self.assertEqual(machines[50].item_id, 339)
        self.assertEqual(machines[57].name, "HM08")
        self.assertEqual(machines[57].table_index, 57)

    def test_rejects_wrong_size_or_invalid_move_id(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_machine_move_table(b"short")
        data = bytearray(struct.pack("<58H", *range(1, 59)))
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


class ParseTmhmLearnsetTests(unittest.TestCase):
    def test_decodes_bits_and_masks(self) -> None:
        # Real Bulbasaur/Ivysaur mask (see constants.py's MACHINE_LEARNSET_SIZE
        # comment): TM06/09/10/11/17/19/21/22/27/32/36/42/43/44/45, HM01/04/05/06.
        data = struct.pack("<II", 0x84350720, 0x00E41E08)

        bits, masks = parse_tmhm_learnset(data)

        self.assertEqual(masks, (0x84350720, 0x00E41E08, 0, 0))
        self.assertTrue(bits & (1 << 5))  # TM06
        self.assertTrue(bits & (1 << 50))  # HM01
        self.assertFalse(bits & (1 << 0))  # TM01 not learnable

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_tmhm_learnset(b"short")


if __name__ == "__main__":
    unittest.main()
