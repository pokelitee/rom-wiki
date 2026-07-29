from __future__ import annotations

import unittest

from romwiki.pipeline.trainer_rewards import calculate_base_prize_money


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
        self.assertEqual(payout["multiplier_provenance"]["offset"], 17)

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
                engine="gen4_dppt",
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

    def test_omits_unsupported_engine(self) -> None:
        self.assertIsNone(
            calculate_base_prize_money(
                {"victory_money_multiplier": 12, "party": [{"level": 20}]},
                engine="future",
            )
        )
