from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.scripts import parse_trainer_battle_commands


class B2W2ScriptTests(unittest.TestCase):
    def test_extracts_single_and_multi_literal_trainer_battles(self) -> None:
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

    def test_ignores_variable_referenced_battles(self) -> None:
        body = struct.pack("<HHHHH", 0x0085, 0x8022, 0, 0, 0x008D)

        self.assertEqual(parse_trainer_battle_commands(body, trainer_count=1000), ())

    def test_resolves_battles_that_handle_their_own_result(self) -> None:
        # Only 59 of B2W2's 180 battle sites with valid trainer operands are
        # followed by the win check; the rest continue with another real
        # command (here VMRegMov). Requiring the win check would drop those.
        body = struct.pack("<HHHHH", 0x0085, 13, 0, 0, 0x0016)

        commands = parse_trainer_battle_commands(body, trainer_count=1000)

        self.assertEqual([command.trainer_ids for command in commands], [(13,)])

    def test_rejects_a_follow_on_that_is_not_a_real_command(self) -> None:
        body = struct.pack("<HHHHH", 0x0085, 13, 0, 0, 0x9999)

        self.assertEqual(parse_trainer_battle_commands(body, trainer_count=1000), ())

    def test_rejects_out_of_range_trainer_ids(self) -> None:
        body = struct.pack("<HHHHH", 0x0085, 9999, 0, 0, 0x008D)

        self.assertEqual(parse_trainer_battle_commands(body, trainer_count=1000), ())

    def test_rejects_a_truncated_multi_battle_signature(self) -> None:
        body = struct.pack("<HHHH", 0x0086, 5, 30, 31)  # missing flags + follow-on

        self.assertEqual(parse_trainer_battle_commands(body, trainer_count=1000), ())


if __name__ == "__main__":
    unittest.main()
