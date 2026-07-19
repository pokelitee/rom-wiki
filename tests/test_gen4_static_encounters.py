from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import parse_static_encounter_commands


def make_script(body: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + body


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
