from __future__ import annotations

import unittest

from romwiki.engines.gen5_bw.machines import machine_name


class Gen5MachineTests(unittest.TestCase):
    def test_names_tms(self) -> None:
        self.assertEqual(machine_name(1), "TM01")
        self.assertEqual(machine_name(95), "TM95")

    def test_names_hms(self) -> None:
        self.assertEqual(machine_name(96), "HM01")
        self.assertEqual(machine_name(101), "HM06")

    def test_falls_back_beyond_known_range(self) -> None:
        self.assertEqual(machine_name(102), "MACHINE102")


if __name__ == "__main__":
    unittest.main()
