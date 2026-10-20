from __future__ import annotations

import unittest
from typing import Any

from romwiki.engines.gen5.shared.starter_branches import Gen5StarterBranchFamily
from romwiki.engines.gen5.shared.starter_families import starter_branch_families

_SELECTOR = {
    "starter_species": (495, 498, 501),
    "species_names": {495: "snivy", 498: "tepig", 501: "oshawott"},
}


def _record(trainer_id: int, class_name: str, name: str) -> dict[str, Any]:
    return {
        "trainer_id": trainer_id,
        "class_name": class_name,
        "name": name,
        "party": [{"species_id": 1}],
        "script_references": [{"name": "Floccesy Town"}],
    }


def _family(script_file_id: int, ids: tuple[int, int, int]) -> Gen5StarterBranchFamily:
    return Gen5StarterBranchFamily(
        script_file_id=script_file_id,
        position=0,
        selected=((0, ids[0]), (1, ids[1])),
        fallthrough_trainer_id=ids[2],
    )


class StarterFamilyTests(unittest.TestCase):
    def _families(self, records, *families):
        return starter_branch_families(
            "test",
            {record["trainer_id"]: record for record in records},
            {**_SELECTOR, "starter_branch_families": families},
        )

    def test_names_a_starter_selected_battle_outside_the_rival_class(self) -> None:
        records = [_record(t, "School Kid", "Seymour") for t in (169, 747, 749)]

        [family] = self._families(records, _family(880, (169, 747, 749)))

        self.assertEqual(family["label"], "Floccesy Town School Kid Seymour battle")

    def test_calls_the_rival_class_a_rival_whatever_its_names(self) -> None:
        records = [
            _record(161, "PKMN Trainer", "Marlon"),
            _record(162, "PKMN Trainer", "Rival"),
            _record(163, "PKMN Trainer", "Rival"),
        ]

        [family] = self._families(records, _family(854, (161, 162, 163)))

        self.assertEqual(family["label"], "Floccesy Town rival battle")

    def test_keeps_one_family_for_a_battle_several_scripts_stage(self) -> None:
        records = [_record(t, "PKMN Trainer", "Rival") for t in (794, 795, 796)]

        families = self._families(
            records,
            _family(1106, (794, 795, 796)),
            _family(1112, (794, 795, 796)),
        )

        self.assertEqual([f["id"] for f in families], ["starter-branch-1106-0"])


if __name__ == "__main__":
    unittest.main()
