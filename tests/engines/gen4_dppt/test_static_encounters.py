from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import parse_static_encounter_commands
from tests.conftest import make_script


class Gen4StaticEncounterTests(unittest.TestCase):
    def test_extracts_literal_wild_battle_followed_by_win_check(self) -> None:
        body = struct.pack("<4H", 0x0124, 479, 20, 0x00EC)

        encounters = parse_static_encounter_commands(
            make_script(body), species_count=494
        )

        self.assertEqual(
            [
                (encounter.offset, encounter.species_id, encounter.level)
                for encounter in encounters
            ],
            [(6, 479, 20)],
        )

    def test_ignores_command_without_adjacent_win_check(self) -> None:
        body = struct.pack("<4H", 0x0124, 479, 20, 0x001E)
        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=494),
            (),
        )

    def test_extracts_legendary_battle_with_intervening_flag_clear(self) -> None:
        body = struct.pack("<6H", 0x02BD, 480, 60, 0x001F, 0x008E, 0x00EC)

        encounters = parse_static_encounter_commands(
            make_script(body), species_count=494
        )

        self.assertEqual(
            [
                (
                    encounter.offset,
                    encounter.species_id,
                    encounter.level,
                    encounter.command,
                )
                for encounter in encounters
            ],
            [(6, 480, 60, "LegendaryBattle")],
        )

    def test_ignores_legendary_opcode_without_battle_result_check(self) -> None:
        body = struct.pack("<4H", 0x02BD, 27, 31, 0x02BE)
        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=494),
            (),
        )

    def test_extracts_specialized_static_battles(self) -> None:
        body = b"".join(
            (
                struct.pack("<6H", 0x0318, 492, 30, 0x001F, 0x008E, 0x00EC),
                struct.pack("<6H", 0x0319, 487, 70, 0x001F, 0x008E, 0x00EC),
            )
        )

        encounters = parse_static_encounter_commands(
            make_script(body), species_count=494
        )

        self.assertEqual(
            [
                (encounter.species_id, encounter.level, encounter.command)
                for encounter in encounters
            ],
            [
                (492, 30, "FatefulEncounter"),
                (487, 70, "GiratinaOriginBattle"),
            ],
        )

    def test_ignores_variable_species_or_level(self) -> None:
        body = b"".join(
            (
                struct.pack("<4H", 0x0124, 0x8004, 20, 0x00EC),
                struct.pack("<4H", 0x0124, 479, 0x8005, 0x00EC),
            )
        )
        self.assertEqual(
            parse_static_encounter_commands(make_script(body), species_count=494),
            (),
        )


if __name__ == "__main__":
    unittest.main()
