from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss.script_opcode_table import OPCODE_TABLE


class Gen4HgssScriptOpcodeTableTests(unittest.TestCase):
    def test_matches_independently_verified_trainer_battle_opcodes(self) -> None:
        # Cross-checked directly against the real HeartGold ROM's script
        # archive (see module docstring): TrainerBattle's real operand is
        # (trainer, var, 1, 1) -- 6 bytes, not the 4-byte (trainer, var)
        # width the project's pre-existing byte-scanner assumed.
        self.assertEqual(OPCODE_TABLE[0xD5], ("TrainerBattle", (2, 2, 1, 1)))
        self.assertEqual(OPCODE_TABLE[0xDC], ("CheckBattleWon", (2,)))

    def test_shares_platinums_low_level_control_flow_opcodes(self) -> None:
        # The disassembler's control-flow-following logic hardcodes these
        # opcode values (script_disassembler.py); HGSS must assign the same
        # numbers to the same VM-level operations for that code to be
        # reusable across engine leaves.
        self.assertEqual(OPCODE_TABLE[0x02][0], "End")
        self.assertEqual(OPCODE_TABLE[0x16][0], "GoTo")
        self.assertEqual(OPCODE_TABLE[0x1A][0], "Call")
        self.assertEqual(OPCODE_TABLE[0x1B][0], "Return")
        self.assertEqual(OPCODE_TABLE[0x1C][0], "GoToIf")
        self.assertEqual(OPCODE_TABLE[0x1D][0], "CallIf")

    def test_matches_known_named_commands_open_items_reference(self) -> None:
        # These specific commands are the ones open-items.md names as the
        # reachable-but-unproven targets for static encounters/gifts/eggs
        # and specialty-shop placement.
        self.assertEqual(OPCODE_TABLE[0x89][0], "GiveMon")
        self.assertEqual(OPCODE_TABLE[0x8A][0], "GiveEgg")
        self.assertEqual(OPCODE_TABLE[0x24D][0], "WildBattle")
        self.assertEqual(OPCODE_TABLE[0x113][0], "MartBuy")
        self.assertEqual(OPCODE_TABLE[0x308][0], "GiveTogepiEgg")
        self.assertEqual(OPCODE_TABLE[0x30A][0], "GiveSpikyEarPichu")

    def test_every_entry_has_only_1_2_or_4_byte_parameters(self) -> None:
        for opcode, (name, widths) in OPCODE_TABLE.items():
            for width in widths:
                self.assertIn(
                    width, (1, 2, 4), f"opcode 0x{opcode:X} ({name}) has width {width}"
                )

    def test_omits_the_five_variable_width_commands(self) -> None:
        # Mirrors Platinum's table's precedent of omitting its own 6
        # variable-width commands (see module docstring).
        for opcode in (0x190, 0x191, 0x192, 0x1D1, 0x1E9):
            self.assertNotIn(opcode, OPCODE_TABLE)

    def test_has_more_commands_than_platinum(self) -> None:
        # HGSS's real dispatch table has 853 entries against Platinum's 839
        # (open-items.md's HGSS script-decoding appendix); this table's
        # highest real opcode (0x354) exceeds `SCRIPT_COMMAND_COUNT`
        # (0x33A, Platinum's own independently-known command count) --
        # expected, not a bound this table should be clamped to.
        self.assertEqual(max(OPCODE_TABLE), 0x354)


if __name__ == "__main__":
    unittest.main()
