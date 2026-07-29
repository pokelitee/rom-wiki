from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import parse_trainer_battle_commands
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script


class Gen4ScriptTests(unittest.TestCase):
    def test_extracts_single_and_double_literal_trainer_battles(self) -> None:
        body = (
            struct.pack("<HHHH", 0xE5, 250, 0, 0xEC)
            + struct.pack("<H", 0x800C)
            + struct.pack("<HHHH", 0xE5, 536, 551, 0xEC)
            + struct.pack("<H", 0x800C)
        )

        commands = parse_trainer_battle_commands(make_script(body), trainer_count=1000)

        self.assertEqual([command.offset for command in commands], [6, 16])
        self.assertEqual(commands[0].trainer_ids, (250,))
        self.assertEqual(commands[1].trainer_ids, (536, 551))

    def test_ignores_variables_and_unverified_opcode_values(self) -> None:
        body = struct.pack("<HHHH", 0xE5, 0x8004, 0, 0xEC) + struct.pack(
            "<HHHH", 0xE5, 250, 0, 0x16
        )
        self.assertEqual(
            parse_trainer_battle_commands(make_script(body), trainer_count=1000),
            (),
        )

    def test_accepts_a_script_table_without_the_optional_terminator(self) -> None:
        body = struct.pack("<HHHH", 0xE5, 250, 0, 0xEC)
        data = struct.pack("<i", 0) + body

        commands = parse_trainer_battle_commands(data, trainer_count=1000)

        self.assertEqual(commands[0].offset, 4)
        self.assertEqual(commands[0].trainer_ids, (250,))

    def test_rejects_invalid_script_table_target(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_trainer_battle_commands(
                struct.pack("<iH", 999, 0xFD13), trainer_count=1000
            )


if __name__ == "__main__":
    unittest.main()
