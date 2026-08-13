from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import parse_rematch_table
from romwiki.engines.gen4.dppt.battle_variants import resolve_trainer_variants
from romwiki.util.errors import InvalidRomError


def _record(base: int, *slots: int) -> bytes:
    padded = (*slots, *(0,) * (5 - len(slots)))
    return struct.pack("<6H", base, *padded)


class Gen4RematchTableTests(unittest.TestCase):
    def test_decodes_stage_slots_and_skips_sentinels(self) -> None:
        # Slot 1 holds no distinct record; slots 2 and 4 do. This is the retail
        # shape for a trainer that is only upgraded later in the story.
        data = _record(45, 0xFFFF, 630, 0xFFFF, 632)

        chains = parse_rematch_table(data, count=1, trainer_count=928)

        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0].base_trainer_id, 45)
        self.assertEqual(chains[0].stages, ((2, 630), (4, 632)))
        self.assertEqual(chains[0].trainer_ids, (45, 630, 632))
        self.assertTrue(chains[0].has_distinct_records)

    def test_treats_self_reference_as_an_unchanged_party(self) -> None:
        chains = parse_rematch_table(_record(14, 14), count=1, trainer_count=928)

        self.assertEqual(chains[0].stages, ((1, 14),))
        self.assertFalse(chains[0].has_distinct_records)

    def test_rejects_a_stage_after_the_terminator(self) -> None:
        data = _record(1, 765, 0, 767)

        with self.assertRaisesRegex(InvalidRomError, "stage after its terminator"):
            parse_rematch_table(data, count=1, trainer_count=928)

    def test_rejects_a_reused_stage_record(self) -> None:
        data = _record(1, 765) + _record(2, 765)

        with self.assertRaisesRegex(InvalidRomError, "reuses stage trainer 765"):
            parse_rematch_table(data, count=2, trainer_count=928)

    def test_rejects_a_repeated_base_trainer(self) -> None:
        data = _record(1, 765) + _record(1, 766)

        with self.assertRaisesRegex(InvalidRomError, "repeats base trainer 1"):
            parse_rematch_table(data, count=2, trainer_count=928)

    def test_rejects_out_of_range_identifiers(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "invalid base trainer"):
            parse_rematch_table(_record(940, 1), count=1, trainer_count=928)
        with self.assertRaisesRegex(InvalidRomError, "slot 1 has invalid trainer"):
            parse_rematch_table(_record(1, 940), count=1, trainer_count=928)

    def test_rejects_a_truncated_table(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "has size 12; expected 24"):
            parse_rematch_table(_record(1, 765), count=2, trainer_count=928)


class Gen4VsSeekerFamilyTests(unittest.TestCase):
    PARAMETERS = {"trainer_variant_contract": "platinum-retail-v1"}

    def _records(self, *trainer_ids: int) -> list[dict[str, object]]:
        return [
            {
                "trainer_id": trainer_id,
                "party": [{"species_id": 1}],
                "class_name": "Artist",
                "name": "William",
            }
            for trainer_id in trainer_ids
        ]

    def _families(self, chains, records):
        result = resolve_trainer_variants(
            "platinum-us",
            self.PARAMETERS,
            records,
            selector_data={"rematch_chains": chains},
        )
        return [
            family
            for family in result["battle_families"]
            if family["id"].startswith("vs-seeker-")
        ]

    def test_enumerates_each_stage_as_a_rematch_variant(self) -> None:
        chains = parse_rematch_table(
            _record(45, 0xFFFF, 630, 0xFFFF, 632), count=1, trainer_count=928
        )

        families = self._families(chains, self._records(45, 630, 632))

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(family["id"], "vs-seeker-0045")
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]], [45, 630, 632]
        )
        self.assertEqual(
            [variant["conditions"][0]["value"] for variant in family["variants"]],
            ["initial", "rematch-2", "rematch-4"],
        )

    def test_omits_chains_that_only_reselect_their_base(self) -> None:
        chains = parse_rematch_table(_record(14, 14), count=1, trainer_count=928)

        self.assertEqual(self._families(chains, self._records(14)), [])

    def test_omits_stages_whose_records_are_absent(self) -> None:
        chains = parse_rematch_table(_record(45, 630, 632), count=1, trainer_count=928)

        # 632 has no party in this profile, so it cannot become a variant.
        families = self._families(chains, self._records(45, 630))

        self.assertEqual(
            [variant["trainer_id"] for variant in families[0]["variants"]], [45, 630]
        )

    def test_reports_rematch_coverage_as_partial(self) -> None:
        result = resolve_trainer_variants(
            "platinum-us", self.PARAMETERS, self._records(45), selector_data=None
        )

        support = result["trainer_variant_support"]["rematch_stage"]
        self.assertEqual(support["status"], "partial")
        self.assertIn("not a pursued axis", support["note"])


if __name__ == "__main__":
    unittest.main()
