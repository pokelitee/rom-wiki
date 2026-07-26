from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.encounters import (
    SEASON_BLOCK_SIZE,
    SEASONS,
    parse_encounter_entry,
)
from romwiki.util.errors import InvalidRomError


def _make_block(
    rates: dict[str, int], slots: dict[str, list[tuple[int, int, int, int]]]
) -> bytes:
    from romwiki.engines.gen5_bw.encounters import METHOD_NAMES, METHOD_SLOT_COUNTS

    block = bytearray(SEASON_BLOCK_SIZE)
    cursor = 8
    for name, count in zip(METHOD_NAMES, METHOD_SLOT_COUNTS, strict=True):
        block[METHOD_NAMES.index(name)] = rates.get(name, 0)
        method_slots = slots.get(name, [])
        for index in range(count):
            base = cursor + index * 4
            if method_slots:
                # Real ROM data fills every slot for an active method (often
                # by repeating a species across several slots); repeat the
                # last given value rather than leaving trailing slots zeroed.
                species_id, form_id, minimum_level, maximum_level = method_slots[
                    min(index, len(method_slots) - 1)
                ]
                struct.pack_into("<H", block, base, species_id | (form_id << 11))
                block[base + 2] = minimum_level
                block[base + 3] = maximum_level
        cursor += count * 4
    return bytes(block)


class Gen5EncounterTests(unittest.TestCase):
    def test_decodes_a_single_season_entry(self) -> None:
        # Real Black ROM member 2 (non-seasonal-style single block), Grass/
        # Cave rate 8: Palpitoad (536) and Shelmet (616) at level 30.
        data = _make_block(
            {"grass_cave": 8, "surfing": 3},
            {
                "grass_cave": [(536, 0, 30, 30), (616, 0, 30, 30)],
                "surfing": [(618, 0, 15, 35)],
            },
        )
        areas = parse_encounter_entry(data, map_index=2, archive_path="wild.narc")

        self.assertEqual(len(areas), 1)
        area = areas[0]
        self.assertIsNone(area.season)
        self.assertEqual(area.map_index, 2)
        self.assertEqual(area.grass_cave.rate, 8)
        self.assertEqual(area.grass_cave.slots[0].species_id, 536)
        self.assertEqual(area.grass_cave.slots[0].minimum_level, 30)
        self.assertEqual(area.surfing.rate, 3)
        self.assertEqual(area.surfing.slots[0].species_id, 618)
        self.assertEqual(area.doubles_grass.rate, 0)
        self.assertEqual(area.provenance.member, 2)

    def test_decodes_four_seasonal_blocks(self) -> None:
        blocks = [
            _make_block({"grass_cave": index + 1}, {"grass_cave": [(504, 0, 5, 5)]})
            for index in range(4)
        ]
        data = b"".join(blocks)

        areas = parse_encounter_entry(data, map_index=7, archive_path="wild.narc")

        self.assertEqual(len(areas), 4)
        self.assertEqual([area.season for area in areas], list(SEASONS))
        self.assertEqual([area.grass_cave.rate for area in areas], [1, 2, 3, 4])
        self.assertTrue(all(area.map_index == 7 for area in areas))

    def test_decodes_a_forme_bit(self) -> None:
        # Basculin's two color-stripe formes share species ID 550; the high
        # 5 bits of the word are the forme index.
        data = _make_block({"fishing": 50}, {"fishing": [(550, 1, 5, 20)]})
        areas = parse_encounter_entry(data, map_index=0, archive_path="wild.narc")
        slot = areas[0].fishing.slots[0]
        self.assertEqual(slot.species_id, 550)
        self.assertEqual(slot.form_id, 1)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_encounter_entry(b"short", map_index=0, archive_path="wild.narc")

    def test_rejects_invalid_species_id_when_rate_is_nonzero(self) -> None:
        data = _make_block({"grass_cave": 1}, {"grass_cave": [(0, 0, 1, 1)]})
        with self.assertRaises(InvalidRomError):
            parse_encounter_entry(data, map_index=0, archive_path="wild.narc")


if __name__ == "__main__":
    unittest.main()
