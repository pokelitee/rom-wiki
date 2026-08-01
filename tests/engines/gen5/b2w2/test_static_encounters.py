from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.static_encounters import discover_static_encounters


class B2W2StaticEncounterTests(unittest.TestCase):
    def test_discovers_reachable_battles_gifts_egg_and_fossils(self) -> None:
        files = {
            0: _script(_fossil_mapping(105, 408) + _fossil_mapping(104, 410) + _party_add(32803, 25)),
            1: _script(
                _wild_battle(638, 65)
                + _wild_battle(638, 45)
                + _wild_battle_ex(646, 55, 1)
                + _wild_battle_ex(612, 60, 0)
                + _party_add_n(570, 25)
                + _party_add_ex(585, 30)
                + _party_add_ex(585, 30)
                + _party_add_egg(440)
            ),
            2: _script(struct.pack("<H", 0x0) + _party_add_ex(585, 30)),
        }

        encounters = discover_static_encounters(
            files.__getitem__,
            member_count=3,
            archive_path="a/0/5/6",
            species_count=650,
            item_count=639,
        )

        self.assertEqual(
            {(value.species_id, value.level, value.is_egg) for value in encounters},
            {
                (408, 25, False),
                (410, 25, False),
                (638, 45, False),
                (612, 60, False),
                (570, 25, False),
                (585, 30, False),
                (440, None, True),
            },
        )
        self.assertEqual(len(encounters), 8)
        self.assertEqual(sum(value.is_egg for value in encounters), 1)
        self.assertEqual(sum(value.species_id == 585 for value in encounters), 2)
        self.assertTrue(all(value.provenance.archive == "a/0/5/6" for value in encounters))


def _script(code: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + code + struct.pack("<H", 0x2)


def _wild_battle(species: int, level: int) -> bytes:
    return struct.pack("<H3H", 0x174, species, level, 0x8000)


def _wild_battle_ex(species: int, level: int, form: int) -> bytes:
    return struct.pack("<H4H", 0x297, species, level, form, 0x8000)


def _party_add(species: int, level: int) -> bytes:
    return struct.pack("<H4H", 0x10C, 0x8010, species, 0, level)


def _party_add_ex(species: int, level: int) -> bytes:
    return struct.pack(
        "<H9H", 0x10E, 0x8010, species, 0, level, 3, 0, 0, 0, 4
    )


def _party_add_n(species: int, level: int) -> bytes:
    return struct.pack("<H6H", 0x2EA, 0x8010, species, level, 11, 0, 0)


def _party_add_egg(species: int) -> bytes:
    return struct.pack("<H3H", 0x10F, 0x8010, species, 0)


def _fossil_mapping(item: int, species: int) -> bytes:
    return (
        struct.pack("<HH", 0x9, 32802)
        + struct.pack("<HH", 0x8, item)
        + struct.pack("<HH", 0x11, 1)
        + struct.pack("<HB", 0x1F, 0xFF)
        + struct.pack("<i", 0)
        + struct.pack("<HHH", 0x28, 32803, species)
    )


if __name__ == "__main__":
    unittest.main()
