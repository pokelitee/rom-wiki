from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss import (
    parse_static_encounter_commands,
    parse_trainer_battle_commands,
)
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script


class Gen4HgssScriptTests(unittest.TestCase):
    def test_extracts_single_and_double_literal_trainer_battles(self) -> None:
        body = (
            struct.pack("<HHHH", 0xD5, 250, 0, 0xDC)
            + struct.pack("<H", 0x800C)
            + struct.pack("<HHHH", 0xD5, 536, 551, 0xDC)
            + struct.pack("<H", 0x800C)
        )

        commands = parse_trainer_battle_commands(make_script(body), trainer_count=1000)

        self.assertEqual([command.offset for command in commands], [6, 16])
        self.assertEqual(commands[0].trainer_ids, (250,))
        self.assertEqual(commands[1].trainer_ids, (536, 551))

    def test_ignores_variable_supplied_trainer_ids(self) -> None:
        body = struct.pack("<HHHH", 0xD5, 0x8004, 0, 0xDC)

        self.assertEqual(
            parse_trainer_battle_commands(make_script(body), trainer_count=1000),
            (),
        )

    def test_resolves_battles_that_handle_their_own_result(self) -> None:
        body = struct.pack("<HHHH", 0xD5, 250, 0, 0x16) + struct.pack(
            "<HHHH", 0xD5, 261, 0, 0x1B
        )

        commands = parse_trainer_battle_commands(make_script(body), trainer_count=1000)

        self.assertEqual(
            [command.trainer_ids for command in commands], [(250,), (261,)]
        )

    def test_ignores_a_follow_on_that_is_not_a_real_command(self) -> None:
        body = struct.pack("<HHHH", 0xD5, 250, 0, 0x9999)

        self.assertEqual(
            parse_trainer_battle_commands(make_script(body), trainer_count=1000),
            (),
        )

    def test_ignores_platinums_own_opcode(self) -> None:
        # HGSS uses a different numeric ID (0x00D5, not Platinum's 0x00E5)
        # for the same command -- confirm the two aren't cross-recognized.
        body = struct.pack("<HHHH", 0xE5, 250, 0, 0xEC)

        self.assertEqual(
            parse_trainer_battle_commands(make_script(body), trainer_count=1000),
            (),
        )

    def test_rejects_invalid_script_table_target(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_trainer_battle_commands(
                struct.pack("<iH", 999, 0xFD13), trainer_count=1000
            )


class Gen4HgssStaticEncounterTests(unittest.TestCase):
    def test_extracts_the_real_clearflag_shape(self) -> None:
        # The exact real byte shape confirmed against the live HeartGold
        # ROM's script archive (see gen4/hgss/scripts.py's module comment):
        # WildBattle(species, level, flag), ClearFlag(id), CheckBattleWon.
        # This mirrors the real Cerulean Cave Mewtwo encounter byte-for-byte
        # (species 150, level 70, flag 0, clear-flag id 0x00A4).
        body = (
            struct.pack("<HHHB", 0x24D, 150, 70, 0)
            + struct.pack("<HH", 0x1F, 0x00A4)
            + struct.pack("<H", 0xDC)
        )

        commands = parse_static_encounter_commands(make_script(body), species_count=650)

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].species_id, 150)
        self.assertEqual(commands[0].level, 70)
        self.assertEqual(commands[0].command, "WildBattle")

    def test_extracts_the_direct_check_shape(self) -> None:
        body = struct.pack("<HHHB", 0x24D, 25, 10, 0) + struct.pack("<H", 0xDC)

        commands = parse_static_encounter_commands(make_script(body), species_count=650)

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].species_id, 25)
        self.assertEqual(commands[0].level, 10)

    def test_ignores_variable_supplied_species(self) -> None:
        body = struct.pack("<HHHB", 0x24D, 0x8004, 70, 0) + struct.pack("<H", 0xDC)

        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=650), ()
        )

    def test_ignores_an_invalid_level(self) -> None:
        body = struct.pack("<HHHB", 0x24D, 150, 0, 0) + struct.pack("<H", 0xDC)

        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=650), ()
        )

    def test_ignores_a_follow_on_that_is_not_a_real_command(self) -> None:
        body = struct.pack("<HHHB", 0x24D, 150, 70, 0) + struct.pack("<H", 0x9999)

        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=650), ()
        )

    def test_ignores_clearflag_not_followed_by_check_battle_won(self) -> None:
        body = (
            struct.pack("<HHHB", 0x24D, 150, 70, 0)
            + struct.pack("<HH", 0x1F, 0x00A4)
            + struct.pack("<H", 0x16)
        )

        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=650), ()
        )


if __name__ == "__main__":
    unittest.main()
