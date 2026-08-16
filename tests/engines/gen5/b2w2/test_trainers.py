from __future__ import annotations

import unittest

from romwiki.engines.gen5.b2w2.trainers import (
    resolve_common_script_trainer_id,
    trainer_name_index,
)


class B2W2TrainersTests(unittest.TestCase):
    def test_trainer_name_index_retains_entry_zero(self) -> None:
        # Unlike BW, which omits message table entry zero and so subtracts
        # one, B2W2's own trainer-name message table retains it -- the
        # trainer ID is used as-is.
        self.assertEqual(trainer_name_index(1), 1)
        self.assertEqual(trainer_name_index(42), 42)

    def test_does_not_apply_bws_common_script_arithmetic(self) -> None:
        # BW's sight-triggered-battle band arithmetic was verified against
        # real Black ROM data specifically; it must not be silently applied
        # to B2W2, which has its own (undecoded) selector convention.
        self.assertIsNone(resolve_common_script_trainer_id(3026, trainer_count=616))
        self.assertIsNone(resolve_common_script_trainer_id(0, trainer_count=616))


if __name__ == "__main__":
    unittest.main()
