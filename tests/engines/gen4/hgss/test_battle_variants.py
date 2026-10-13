from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss.battle_variants import resolve_trainer_variants
from romwiki.engines.gen4.shared.starter_branches import Gen4StarterBranchFamily

_CONTRACT = "hgss-retail-v1"


def _record(trainer_id: int) -> dict:
    return {"trainer_id": trainer_id, "party": [{"species_id": 1}]}


class HgssBattleVariantsTests(unittest.TestCase):
    def test_names_the_fallthrough_species_by_elimination(self) -> None:
        family = Gen4StarterBranchFamily(
            script_file_id=2,
            position=0,
            selected=((155, 101), (158, 102)),
            fallthrough_trainer_id=103,
        )
        result = resolve_trainer_variants(
            "heartgold-us",
            {"trainer_variant_contract": _CONTRACT},
            [_record(101), _record(102), _record(103)],
            selector_data={
                "starter_branch_families": (family,),
                "species_names": {155: "Cyndaquil", 158: "Totodile", 152: "Chikorita"},
                "starter_species": (152, 155, 158),
            },
        )

        variants = result["battle_families"][0]["variants"]
        fallthrough = next(v for v in variants if v["trainer_id"] == 103)
        self.assertEqual(fallthrough["conditions"][0]["value"], "chikorita")
        self.assertEqual(
            fallthrough["conditions"][0]["label"], "Player chose Chikorita"
        )

    def test_falls_back_to_a_generic_label_without_starter_species(self) -> None:
        family = Gen4StarterBranchFamily(
            script_file_id=2,
            position=0,
            selected=((155, 101), (158, 102)),
            fallthrough_trainer_id=103,
        )
        result = resolve_trainer_variants(
            "heartgold-us",
            {"trainer_variant_contract": _CONTRACT},
            [_record(101), _record(102), _record(103)],
            selector_data={
                "starter_branch_families": (family,),
                "species_names": {155: "Cyndaquil", 158: "Totodile", 152: "Chikorita"},
            },
        )

        variants = result["battle_families"][0]["variants"]
        fallthrough = next(v for v in variants if v["trainer_id"] == 103)
        self.assertEqual(fallthrough["conditions"][0]["value"], "remaining-starter")


if __name__ == "__main__":
    unittest.main()
