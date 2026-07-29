from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import (
    parse_egg_gift_command,
    parse_pokemon_gift_commands,
)
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_script


class Gen4GiftTests(unittest.TestCase):
    def test_extracts_literal_pokemon_gift(self) -> None:
        body = struct.pack("<5H", 0x0096, 133, 5, 0, 0x800C)

        gifts = parse_pokemon_gift_commands(
            make_script(body), species_count=494, item_count=468
        )

        self.assertEqual(
            [
                (gift.offset, gift.species_id, gift.level, gift.held_item_id)
                for gift in gifts
            ],
            [(6, 133, 5, 0)],
        )

    def test_ignores_variable_species_gift(self) -> None:
        body = struct.pack("<5H", 0x0096, 0x8004, 5, 0, 0x800C)
        self.assertEqual(
            parse_pokemon_gift_commands(
                make_script(body), species_count=494, item_count=468
            ),
            (),
        )

    def test_parses_profile_anchored_egg_gift(self) -> None:
        script = make_script(struct.pack("<3H", 0x0097, 175, 11))
        gift = parse_egg_gift_command(script, offset=6, species_count=494)
        self.assertEqual((gift.species_id, gift.offset), (175, 6))

    def test_rejects_wrong_anchored_egg_command(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_egg_gift_command(
                make_script(struct.pack("<3H", 0x0096, 175, 11)),
                offset=6,
                species_count=494,
            )


if __name__ == "__main__":
    unittest.main()
