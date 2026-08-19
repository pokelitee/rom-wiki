from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss import (
    parse_egg_gift_commands,
    parse_pokemon_gift_commands,
    parse_togepi_egg_gift_commands,
)
from tests.conftest import make_script


class Gen4HgssGiftTests(unittest.TestCase):
    def test_extracts_literal_pokemon_gift(self) -> None:
        body = struct.pack("<7H", 0x0089, 133, 5, 0, 0, 0, 0x800C)

        gifts = parse_pokemon_gift_commands(make_script(body), species_count=494)

        self.assertEqual(
            [(gift.offset, gift.species_id, gift.level) for gift in gifts],
            [(6, 133, 5)],
        )

    def test_ignores_variable_species_gift(self) -> None:
        body = struct.pack("<7H", 0x0089, 0x8004, 5, 0, 0, 0, 0x800C)
        self.assertEqual(
            parse_pokemon_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_ignores_gift_missing_output_variable(self) -> None:
        body = struct.pack("<7H", 0x0089, 133, 5, 0, 0, 0, 0x0001)
        self.assertEqual(
            parse_pokemon_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_ignores_out_of_range_level(self) -> None:
        body = struct.pack("<7H", 0x0089, 133, 0, 0, 0, 0, 0x800C)
        self.assertEqual(
            parse_pokemon_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_ignores_unrelated_opcode(self) -> None:
        body = struct.pack("<7H", 0x0090, 133, 5, 0, 0, 0, 0x800C)
        self.assertEqual(
            parse_pokemon_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_ignores_unreachable_gift(self) -> None:
        # A real End (0x0002) terminates the only reachable function; the
        # GiveMon-shaped bytes after it are never disassembled from any real
        # function offset, so they must not be reported.
        body = struct.pack("<H", 0x0002) + struct.pack(
            "<7H", 0x0089, 133, 5, 0, 0, 0, 0x800C
        )
        self.assertEqual(
            parse_pokemon_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_extracts_literal_egg_gift(self) -> None:
        body = struct.pack("<3H", 0x008A, 179, 0x800C) + struct.pack("<H", 0x0002)

        gifts = parse_egg_gift_commands(make_script(body), species_count=494)

        self.assertEqual(
            [(gift.offset, gift.species_id) for gift in gifts],
            [(6, 179)],
        )

    def test_ignores_out_of_range_egg_species(self) -> None:
        body = struct.pack("<3H", 0x008A, 0, 0x800C) + struct.pack("<H", 0x0002)
        self.assertEqual(
            parse_egg_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_ignores_unreachable_egg_gift(self) -> None:
        body = struct.pack("<H", 0x0002) + struct.pack("<3H", 0x008A, 179, 0x800C)
        self.assertEqual(
            parse_egg_gift_commands(make_script(body), species_count=494),
            (),
        )

    def test_extracts_reachable_togepi_egg_gift(self) -> None:
        body = struct.pack("<H", 0x0308) + struct.pack("<H", 0x0002)

        gifts = parse_togepi_egg_gift_commands(make_script(body))

        self.assertEqual([gift.offset for gift in gifts], [6])

    def test_ignores_unreachable_togepi_egg_gift(self) -> None:
        body = struct.pack("<H", 0x0002) + struct.pack("<H", 0x0308)
        self.assertEqual(parse_togepi_egg_gift_commands(make_script(body)), ())


if __name__ == "__main__":
    unittest.main()
