from __future__ import annotations

import unittest

from romwiki.engines.gen5.shared.trainer_records import (
    TRAINER_RECORD_SIZE,
    parse_trainer_record,
)
from romwiki.pipeline.enrichment.trainer_rewards import (
    BATTLE_MODE_VICTORY_MONEY_MULTIPLIER_OFFSET,
    calculate_base_prize_money,
)
from romwiki.util.errors import DataSourceError


class TrainerRewardTests(unittest.TestCase):
    def test_calculates_gen5_payout_from_final_party_member(self) -> None:
        payout = calculate_base_prize_money(
            {
                "victory_money_multiplier": 12,
                "party": [{"level": 50}, {"level": 20}],
            },
            engine="gen5_bw",
        )

        self.assertEqual(
            payout,
            {
                "amount": 960,
                "final_party_level": 20,
                "multiplier": 12,
                "base_factor": 4,
                "battle_format_multiplier": 1,
                "multiplier_provenance": None,
            },
        )

    def test_calculates_b2w2_payout_with_gen5_rules(self) -> None:
        payout = calculate_base_prize_money(
            {
                "victory_money_multiplier": 10,
                "party": [{"level": 25}],
                "provenance": {"archive": "a/0/9/1", "member": 1},
            },
            engine="gen5_b2w2",
        )

        self.assertEqual(payout["amount"], 1000)
        self.assertEqual(
            payout["multiplier_provenance"]["offset"],
            BATTLE_MODE_VICTORY_MONEY_MULTIPLIER_OFFSET,
        )

    def test_omits_payout_when_an_exact_input_is_missing(self) -> None:
        self.assertIsNone(
            calculate_base_prize_money(
                {"victory_money_multiplier": 12, "party": []},
                engine="gen5_bw",
            )
        )
        self.assertIsNone(
            calculate_base_prize_money(
                {"party": [{"level": 20}]},
                engine="gen5_bw",
            )
        )

    def test_applies_gen4_double_battle_multiplier(self) -> None:
        self.assertEqual(
            calculate_base_prize_money(
                {
                    "victory_money_multiplier": 12,
                    "party": [{"level": 20}],
                    "double_battle": True,
                },
                engine="gen4_platinum",
            ),
            {
                "amount": 1920,
                "final_party_level": 20,
                "multiplier": 12,
                "base_factor": 4,
                "battle_format_multiplier": 2,
                "multiplier_provenance": None,
            },
        )

    def test_applies_gen3_double_battle_multiplier(self) -> None:
        payout = calculate_base_prize_money(
            {
                "victory_money_multiplier": 25,
                "party": [{"level": 14}],
                "double_battle": True,
            },
            engine="gen3_frlg",
        )
        assert payout is not None
        self.assertEqual(
            (payout["amount"], payout["battle_format_multiplier"]), (2800, 2)
        )

    def test_unknown_engine_is_an_error_rather_than_a_missing_payout(self) -> None:
        with self.assertRaises(DataSourceError):
            calculate_base_prize_money(
                {"victory_money_multiplier": 12, "party": [{"level": 20}]},
                engine="future",
            )

    def test_records_the_gen5_multiplier_byte_the_decoder_reads(self) -> None:
        record = bytearray(TRAINER_RECORD_SIZE)
        record[BATTLE_MODE_VICTORY_MONEY_MULTIPLIER_OFFSET] = 0xA5
        trainer = parse_trainer_record(
            bytes(record),
            b"",
            trainer_id=1,
            name="Trainer",
            class_names=("Class",),
            trainer_archive="a/0/9/1",
            party_archive="a/0/9/2",
        )

        self.assertEqual(trainer.victory_money_multiplier, 0xA5)
