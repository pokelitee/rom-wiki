from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.scripts import parse_trainer_battle_commands


class Gen5ScriptTests(unittest.TestCase):
    def test_extracts_single_and_multi_literal_trainer_battles(self) -> None:
        # Real Black ROM shape: `CallTrainerBattle(trId1, trId2, flags)`
        # immediately followed by `TrainerBattleIsVictory` -- verified
        # against 12 real occurrences in the ROM, always adjacent this way.
        body = (
            struct.pack("<HHHHH", 0x0085, 13, 0, 0, 0x008D)
            + struct.pack("<H", 0x8010)
            + struct.pack("<HHHHHH", 0x0086, 5, 30, 31, 0, 0x008D)
            + struct.pack("<H", 0x8010)
        )

        commands = parse_trainer_battle_commands(body, trainer_count=1000)

        self.assertEqual([command.offset for command in commands], [0, 12])
        self.assertEqual(commands[0].trainer_ids, (13,))
        self.assertEqual(commands[1].trainer_ids, (5, 30, 31))

    def test_ignores_variable_referenced_and_unverified_battles(self) -> None:
        body = (
            struct.pack("<HHHHH", 0x0085, 0x8022, 0, 0, 0x008D)
            + struct.pack("<HHHHH", 0x0085, 13, 0, 0, 0x0016)
        )

        self.assertEqual(
            parse_trainer_battle_commands(body, trainer_count=1000), ()
        )

    def test_rejects_out_of_range_trainer_ids(self) -> None:
        body = struct.pack("<HHHHH", 0x0085, 9999, 0, 0, 0x008D)

        self.assertEqual(
            parse_trainer_battle_commands(body, trainer_count=1000), ()
        )


if __name__ == "__main__":
    unittest.main()
