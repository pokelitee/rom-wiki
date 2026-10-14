from __future__ import annotations

import unittest

from romwiki.schema.trainers import is_unused_trainer_slot


class UnusedTrainerSlotTests(unittest.TestCase):
    def test_recognizes_the_placeholder_class_name(self) -> None:
        self.assertTrue(is_unused_trainer_slot({"class_name": " No Data "}))

    def test_keeps_a_trainer_whose_class_name_is_undecoded(self) -> None:
        self.assertFalse(is_unused_trainer_slot({"class_name": None}))

    def test_keeps_a_trainer_with_a_real_class_name(self) -> None:
        self.assertFalse(is_unused_trainer_slot({"class_name": "Youngster"}))


if __name__ == "__main__":
    unittest.main()
