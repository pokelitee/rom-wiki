from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.battle_variants import resolve_trainer_variants
from romwiki.schema.trainers import validate_trainer_battle_families


class ResolveTrainerVariantsTests(unittest.TestCase):
    def test_reports_every_mechanic_unresolved_with_no_battle_families(self) -> None:
        result = resolve_trainer_variants("firered-us", {}, [{"trainer_id": 1}])

        self.assertEqual(result["battle_families"], [])
        support = result["trainer_variant_support"]
        self.assertEqual(
            {mechanic["status"] for mechanic in support.values()}, {"unresolved"}
        )

    def test_result_satisfies_the_shared_validation_contract(self) -> None:
        result = resolve_trainer_variants("firered-us", {}, [{"trainer_id": 1}])

        validate_trainer_battle_families(
            result["battle_families"], result["trainer_variant_support"], [1]
        )


if __name__ == "__main__":
    unittest.main()
