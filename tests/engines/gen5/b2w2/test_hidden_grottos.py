from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.hidden_grottos import (
    HIDDEN_GROTTO_DISPATCH_BASE,
    hidden_grotto_id_for_dispatch,
    parse_hidden_grotto_record,
)
from romwiki.util.errors import InvalidRomError


def _record() -> bytes:
    data = bytearray(220)
    for pokemon_group in range(6):
        offset = pokemon_group * 26
        struct.pack_into(
            "<4H", data, offset, *(1 + pokemon_group * 4 + i for i in range(4))
        )
        data[offset + 8 : offset + 12] = bytes((20, 21, 22, 23))
        data[offset + 12 : offset + 16] = bytes((15, 16, 17, 18))
        data[offset + 16 : offset + 20] = bytes((0, 30, 60, 100))
    data[20] = 1
    struct.pack_into("<32H", data, 156, *range(1, 33))
    return bytes(data)


class HiddenGrottoTests(unittest.TestCase):
    def test_decodes_each_version_group_and_item_pool(self) -> None:
        black = parse_hidden_grotto_record(
            _record(),
            grotto_id=3,
            archive_path="a/2/7/3",
            version_group=1,
            species_count=100,
            item_count=100,
            valid_forms=frozenset(),
        )
        self.assertEqual(
            [slot.species_id for slot in black.pokemon[:4]], [13, 14, 15, 16]
        )
        self.assertEqual(
            (black.pokemon[0].minimum_level, black.pokemon[0].maximum_level),
            (15, 20),
        )
        self.assertEqual(black.pokemon[1].female_percentage, 30)
        self.assertEqual(black.pokemon[4].pool_chance, 4)
        self.assertEqual(black.visible_items[4].item_id, 5)
        self.assertEqual(black.visible_items[4].pool_chance, 4)
        self.assertEqual(black.hidden_items[-1].item_id, 32)
        self.assertEqual(black.provenance.member, 3)

        white = parse_hidden_grotto_record(
            _record(),
            grotto_id=3,
            archive_path="a/2/7/3",
            version_group=0,
            species_count=100,
            item_count=100,
            valid_forms=frozenset({(1, 1)}),
        )
        self.assertEqual([slot.species_id for slot in white.pokemon[:4]], [1, 2, 3, 4])
        self.assertEqual(white.pokemon[0].form_id, 1)

    def test_rejects_malformed_records_and_identifiers(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "size 219"):
            parse_hidden_grotto_record(
                _record()[:-1],
                grotto_id=0,
                archive_path="a/2/7/3",
                version_group=0,
                species_count=100,
                item_count=100,
                valid_forms=frozenset({(1, 1)}),
            )
        malformed = bytearray(_record())
        struct.pack_into("<H", malformed, 0, 100)
        with self.assertRaisesRegex(InvalidRomError, "invalid species 100"):
            parse_hidden_grotto_record(
                bytes(malformed),
                grotto_id=0,
                archive_path="a/2/7/3",
                version_group=0,
                species_count=100,
                item_count=100,
                valid_forms=frozenset({(1, 1)}),
            )

    def test_resolves_only_the_verified_dispatch_band(self) -> None:
        self.assertEqual(hidden_grotto_id_for_dispatch(HIDDEN_GROTTO_DISPATCH_BASE), 0)
        self.assertEqual(
            hidden_grotto_id_for_dispatch(HIDDEN_GROTTO_DISPATCH_BASE + 19), 19
        )
        self.assertIsNone(
            hidden_grotto_id_for_dispatch(HIDDEN_GROTTO_DISPATCH_BASE - 1)
        )
        self.assertIsNone(
            hidden_grotto_id_for_dispatch(HIDDEN_GROTTO_DISPATCH_BASE + 20)
        )


if __name__ == "__main__":
    unittest.main()
