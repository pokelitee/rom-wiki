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
            },
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

    def test_omits_unsupported_engine(self) -> None:
        self.assertIsNone(
            calculate_base_prize_money(
                {
                    "victory_money_multiplier": 12,
                    "party": [{"level": 20}],
                },
                engine="gen4_dppt",
            )
        )
