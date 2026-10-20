from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.trainers import (
    PRIZE_TABLE_ROWS,
    parse_trainer_class_prize_multipliers,
)
from romwiki.util.errors import InvalidRomError


def _table(rows: list[tuple[int, int]]) -> bytes:
    padded = rows + [(0xFFFF, 0)] * (PRIZE_TABLE_ROWS - len(rows))
    return b"".join(struct.pack("<HH", *row) for row in padded)


class TrainerPrizeTableTests(unittest.TestCase):
    def test_looks_up_each_class_by_its_row(self) -> None:
        # Rows need not follow class order.
        data = _table([(0, 0), (1, 0), (2, 4), (4, 8), (3, 6)])

        prizes = parse_trainer_class_prize_multipliers(data, count=5)

        self.assertEqual(prizes.multipliers, (0, 0, 4, 6, 8))
        self.assertEqual(prizes.offsets, (2, 6, 10, 18, 14))

    def test_falls_back_to_row_2_for_an_unlisted_class(self) -> None:
        data = _table([(0, 0), (1, 0), (2, 4)])

        prizes = parse_trainer_class_prize_multipliers(data, count=4)

        self.assertEqual(prizes.multipliers[3], 4)
        self.assertEqual(prizes.offsets[3], 10)

    def test_rejects_a_short_table(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "HGSS trainer prize table"):
            parse_trainer_class_prize_multipliers(bytes(8), count=2)


if __name__ == "__main__":
    unittest.main()
