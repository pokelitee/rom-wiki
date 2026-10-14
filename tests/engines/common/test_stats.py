from __future__ import annotations

import unittest

from romwiki.engines.common.stats import (
    SHEDINJA_SPECIES_ID,
    hp_stat,
    nature_decreased_stat,
    nature_increased_stat,
    neutral_stat,
)


class StatFormulaTests(unittest.TestCase):
    def test_hp_uses_the_level_offset_formula(self) -> None:
        # Garchomp (base 108 HP) at level 50 with 31 IVs and 252 EVs.
        self.assertEqual(
            hp_stat(species_id=445, base=108, iv=31, ev=252, level=50), 215
        )

    def test_shedinja_hp_is_always_one(self) -> None:
        self.assertEqual(
            hp_stat(species_id=SHEDINJA_SPECIES_ID, base=1, iv=31, ev=252, level=100),
            1,
        )

    def test_neutral_stat_floors_each_division(self) -> None:
        # Garchomp (base 130 Attack) at level 50 with 31 IVs and 252 EVs.
        self.assertEqual(neutral_stat(base=130, iv=31, ev=252, level=50), 182)
        self.assertEqual(neutral_stat(base=130, iv=0, ev=3, level=1), 7)

    def test_nature_multipliers_floor_after_scaling(self) -> None:
        self.assertEqual(nature_increased_stat(182), 200)
        self.assertEqual(nature_decreased_stat(182), 163)


if __name__ == "__main__":
    unittest.main()
