from __future__ import annotations

import unittest

from romwiki.engines.gen5.bw.static_encounters import _static_fact
from romwiki.engines.gen5.shared.script_disassembler import Gen5Instruction


class Gen5StaticEncounterTests(unittest.TestCase):
    def test_normalizes_literal_script_commands(self) -> None:
        battle = Gen5Instruction(12, 0x178, "CallWildBattle", (637, 70, 0x8000), 20)
        egg = Gen5Instruction(20, 0x10F, "PokePartyAddEgg", (0x8010, 636, 0), 28)

        self.assertEqual(_static_fact(battle, species_count=650), (637, 70, False))
        self.assertEqual(_static_fact(egg, species_count=650), (636, None, True))


if __name__ == "__main__":
    unittest.main()
