from __future__ import annotations

import re
import unittest

import romwiki.schema as schema
from romwiki.schema import Move, RecordProvenance


class PublicSchemaContractTests(unittest.TestCase):
    def test_public_types_are_not_named_for_generations(self) -> None:
        generation_name = re.compile(r"Gen[0-9]+")

        self.assertFalse(
            [name for name in schema.__all__ if generation_name.search(name)]
        )

    def test_optional_move_extensions_do_not_change_unsupported_output(self) -> None:
        move = Move(
            move_id=1,
            effect_id=0,
            damage_class_id=0,
            power=0,
            type_id=0,
            accuracy=0,
            pp=1,
            effect_chance=0,
            target_id=0,
            priority=0,
            flags=0,
            provenance=RecordProvenance(source="rom", archive="moves", member=1),
        )

        self.assertNotIn("contest_effect_id", move.to_dict())
        self.assertNotIn("contest_type_id", move.to_dict())


if __name__ == "__main__":
    unittest.main()
