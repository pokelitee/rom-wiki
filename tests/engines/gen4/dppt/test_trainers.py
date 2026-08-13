from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import (
    Gen4StarterBranchFamily,
    parse_trainer_class_genders,
    parse_trainer_record,
)
from romwiki.engines.gen4.dppt.battle_variants import (
    resolve_trainer_variants,
)
from romwiki.engines.gen4.dppt.trainers import (
    parse_trainer_class_prize_multipliers,
)
from romwiki.util.errors import InvalidRomError


class Gen4TrainerTests(unittest.TestCase):
    def test_decodes_flags_party_forms_and_trailing_data(self) -> None:
        trainer = bytearray(20)
        struct.pack_into("<BBBB4HII", trainer, 0, 3, 2, 7, 1, 5, 0, 0, 0, 9, 2)
        party = (
            struct.pack("<BBHHH4HH", 100, 1, 42, 479 | (2 << 10), 6, 85, 86, 87, 88, 3)
            + b"\xff\xff"
        )

        result = parse_trainer_record(
            bytes(trainer),
            party,
            trainer_id=12,
            name="Tristan",
            class_names=("Pokémon Trainer", "Youngster", "Ace Trainer"),
            class_genders=("female", "male", "male"),
            class_prize_multipliers=(0, 4, 12),
            trainer_archive="trdata.narc",
            party_archive="trpoke.narc",
        )

        self.assertTrue(result.has_custom_moves)
        self.assertTrue(result.has_held_items)
        self.assertTrue(result.double_battle)
        self.assertEqual(result.class_gender, "male")
        self.assertEqual(result.victory_money_multiplier, 12)
        self.assertEqual(result.party[0].species_id, 479)
        self.assertEqual(result.party[0].form_id, 2)
        self.assertEqual(result.party[0].move_ids, (85, 86, 87, 88))
        self.assertEqual(result.trailing_party_data, b"\xff\xff")

    def test_rejects_truncated_party(self) -> None:
        trainer = bytearray(20)
        trainer[3] = 1
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                bytes(trainer),
                b"",
                trainer_id=1,
                name="",
                class_names=("Pokémon Trainer",),
                class_genders=("male",),
                class_prize_multipliers=(0,),
                trainer_archive="trdata.narc",
                party_archive="trpoke.narc",
            )

    def test_omits_unavailable_prize_multiplier(self) -> None:
        trainer = bytearray(20)

        result = parse_trainer_record(
            bytes(trainer),
            b"",
            trainer_id=1,
            name="Silver",
            class_names=("Rival",),
            class_genders=("male",),
            class_prize_multipliers=None,
            trainer_archive="trdata.narc",
            party_archive="trpoke.narc",
        )

        self.assertIsNone(result.victory_money_multiplier)
        self.assertNotIn("victory_money_multiplier", result.to_dict())

    def test_decodes_trainer_class_gender_table(self) -> None:
        self.assertEqual(
            parse_trainer_class_genders(b"\x00\x01\x02", count=3),
            ("male", "female", "male"),
        )
        with self.assertRaisesRegex(InvalidRomError, "unknown values"):
            parse_trainer_class_genders(b"\x03", count=1)

    def test_decodes_trainer_class_prize_multiplier_table(self) -> None:
        self.assertEqual(
            parse_trainer_class_prize_multipliers(b"\x00\x04\x28", count=3),
            (0, 4, 40),
        )
        with self.assertRaisesRegex(InvalidRomError, "has size 2; expected 3"):
            parse_trainer_class_prize_multipliers(b"\x00\x04", count=3)

    @staticmethod
    def _decoded_family(*, script_file_id: int = 429):
        # Whatever the ROM's branches happened to select; nothing about these
        # numbers is known to the resolver in advance.
        return Gen4StarterBranchFamily(
            script_file_id=script_file_id,
            position=0,
            selected=((387, 5001), (390, 5002)),
            fallthrough_trainer_id=5003,
        )

    def _records(self, *, site: str | None = "Relocated Town", ids=(5001, 5002, 5003)):
        return [
            {
                "trainer_id": trainer_id,
                "party": [{"species_id": 1}],
                **({"script_references": [{"name": site}]} if site else {}),
            }
            for trainer_id in ids
        ]

    def _resolve(self, records, family):
        return resolve_trainer_variants(
            "platinum-us",
            {"trainer_variant_contract": "platinum-retail-v1"},
            records,
            selector_data={
                "starter_branch_families": (family,),
                "species_names": {387: "TURTWIG", 390: "CHIMCHAR"},
            },
        )

    def test_builds_a_family_from_the_decoded_branches(self) -> None:
        result = self._resolve(self._records(), self._decoded_family())

        family = result["battle_families"][0]
        self.assertEqual(family["id"], "starter-branch-0429-0")
        self.assertEqual(
            [v["trainer_id"] for v in family["variants"]], [5001, 5002, 5003]
        )
        self.assertEqual(
            [v["conditions"][0]["value"] for v in family["variants"]],
            ["turtwig", "chimchar", "remaining-starter"],
        )

    def test_labels_a_battle_site_from_the_profile_s_own_scripts(self) -> None:
        result = self._resolve(self._records(), self._decoded_family())

        self.assertEqual(
            result["battle_families"][0]["label"], "Relocated Town rival battle"
        )

    def test_falls_back_when_variants_disagree_on_a_battle_site(self) -> None:
        records = [
            {
                "trainer_id": trainer_id,
                "party": [{"species_id": 1}],
                "script_references": [{"name": name}],
            }
            for trainer_id, name in (
                (5001, "One Town"),
                (5002, "Other Town"),
                (5003, "One Town"),
            )
        ]

        result = self._resolve(records, self._decoded_family())

        self.assertEqual(result["battle_families"][0]["label"], "Rival battle")

    def test_does_not_relate_records_without_parties(self) -> None:
        records = [{"trainer_id": trainer_id, "party": []} for trainer_id in (5001,)]

        result = self._resolve(records, self._decoded_family())

        self.assertEqual(result["battle_families"], [])

    def test_reports_nothing_when_no_branches_were_decoded(self) -> None:
        result = resolve_trainer_variants(
            "platinum-us",
            {"trainer_variant_contract": "platinum-retail-v1"},
            self._records(),
            selector_data=None,
        )

        self.assertEqual(result["battle_families"], [])


if __name__ == "__main__":
    unittest.main()
