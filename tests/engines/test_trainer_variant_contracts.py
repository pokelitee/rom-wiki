from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss.battle_variants import (
    resolve_trainer_variants as resolve_hgss,
)
from romwiki.engines.gen4.platinum.battle_variants import (
    resolve_trainer_variants as resolve_platinum,
)
from romwiki.engines.gen5.b2w2.battle_variants import (
    resolve_trainer_variants as resolve_b2w2,
)
from romwiki.engines.gen5.bw.battle_variants import (
    resolve_trainer_variants as resolve_bw,
)
from romwiki.schema.trainers import unverified_trainer_variants
from romwiki.util.errors import ProfileError

_RESOLVERS = {
    "platinum": resolve_platinum,
    "hgss": resolve_hgss,
    "bw": resolve_bw,
    "b2w2": resolve_b2w2,
}
# Includes B2W2's hand-verified rival trainer IDs, which must not be applied
# to a build its contract was not verified against.
_RECORDS = [
    {"trainer_id": trainer_id, "party": [{"species_id": 1}]}
    for trainer_id in (161, 162, 163)
]


class TrainerVariantContractTests(unittest.TestCase):
    def test_a_profile_without_a_contract_publishes_no_families(self) -> None:
        for engine, resolve in _RESOLVERS.items():
            with self.subTest(engine=engine):
                result = resolve("new-hack", {}, _RECORDS)

                self.assertEqual(result, unverified_trainer_variants())
                self.assertEqual(result["battle_families"], [])
                self.assertEqual(
                    {
                        support["status"]
                        for support in result["trainer_variant_support"].values()
                    },
                    {"unresolved"},
                )

    def test_an_unknown_contract_is_still_rejected(self) -> None:
        for engine, resolve in _RESOLVERS.items():
            with (
                self.subTest(engine=engine),
                self.assertRaisesRegex(ProfileError, "verified"),
            ):
                resolve(
                    "new-hack", {"trainer_variant_contract": "misspelled"}, _RECORDS
                )


if __name__ == "__main__":
    unittest.main()
