from __future__ import annotations

import unittest
from unittest.mock import patch

from romwiki.pipeline.enrichment.type_charts import (
    TYPE_CHARTS,
    RegisteredTypeChart,
    TypeChartFamily,
    build_type_dataset,
    defensive_effectiveness,
    validate_type_chart,
)
from romwiki.profiles.models import GameProfile, KnownHash, TypeChartConfig
from romwiki.schema.versions import TYPE_CHART_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, ProfileError


class TypeChartTests(unittest.TestCase):
    def test_calculates_single_and_dual_type_defenses(self) -> None:
        dataset = build_type_dataset(_profile("gen4_platinum", "gen4"))

        water = defensive_effectiveness(dataset, ("water",))
        self.assertIn("electric", water["2"])
        self.assertIn("fire", water["1/2"])

        water_flying = defensive_effectiveness(dataset, ("water", "flying"))
        self.assertIn("electric", water_flying["4"])
        self.assertIn("fighting", water_flying["1/2"])
        self.assertIn("grass", water_flying["1"])

    def test_calculates_quarter_damage_and_immunity(self) -> None:
        dataset = build_type_dataset(_profile("gen5_bw", "gen5"))
        steel_flying = defensive_effectiveness(dataset, ("steel", "flying"))

        self.assertIn("bug", steel_flying["1/4"])
        self.assertIn("ground", steel_flying["0"])

    def test_gen5_chart_supports_b2w2(self) -> None:
        dataset = build_type_dataset(_profile("gen5_b2w2", "gen5"))

        self.assertEqual(dataset["engine"], "gen5_b2w2")
        self.assertIn(
            "electric",
            defensive_effectiveness(dataset, ("water",))["2"],
        )

    def test_keeps_generation_charts_separately_registered(self) -> None:
        self.assertIsNot(TYPE_CHARTS["gen4"], TYPE_CHARTS["gen5"])
        self.assertEqual(TYPE_CHARTS["gen4"].id, "gen4")
        self.assertEqual(TYPE_CHARTS["gen5"].id, "gen5")
        self.assertIs(TYPE_CHARTS["gen4"].family, TYPE_CHARTS["gen5"].family)
        self.assertEqual(TYPE_CHARTS["gen4"].family.id, "gen2-5")

    def test_chart_selection_is_independent_of_extraction_engine(self) -> None:
        dataset = build_type_dataset(_profile("future_engine", "gen2-5"))

        self.assertEqual(dataset["engine"], "future_engine")
        self.assertEqual(dataset["record_count"], 17)

    def test_records_canonical_chart_provenance(self) -> None:
        dataset = build_type_dataset(_profile("gen5_bw", "gen5"))

        self.assertEqual(dataset["schema_version"], TYPE_CHART_SCHEMA_VERSION)
        self.assertEqual(dataset["source_kind"], "engine-canonical")
        self.assertEqual(
            dataset["provenance"],
            {
                "profile": "test",
                "engine": "gen5_bw",
                "chart": "gen5",
                "chart_family": "gen2-5",
                "additional_types": [],
                "overrides": {},
            },
        )

    def test_selected_generation_chart_can_have_different_matchups(self) -> None:
        matrix = dict(TYPE_CHARTS["gen5"].matrix)
        matrix["ghost", "steel"] = "1"
        fixture = RegisteredTypeChart(
            "gen5_bw",
            TypeChartFamily(
                "gen5-fixture",
                TYPE_CHARTS["gen5"].types,
                matrix,
            ),
        )
        with patch.dict(TYPE_CHARTS, {"gen5-fixture": fixture}):
            canonical = build_type_dataset(_profile("gen5_bw", "gen5"))
            changed = build_type_dataset(_profile("gen5_bw", "gen5-fixture"))

        self.assertIn("ghost", defensive_effectiveness(canonical, ("steel",))["1/2"])
        self.assertIn("ghost", defensive_effectiveness(changed, ("steel",))["1"])

    def test_applies_a_hack_addition_and_override(self) -> None:
        profile = _profile(
            "gen4_platinum",
            "gen4",
            additional_types=("fairy",),
            overrides={
                "dragon>fairy": "0",
                "steel>fairy": "2",
                "ghost>steel": "1",
            },
        )
        dataset = build_type_dataset(profile)

        self.assertEqual(dataset["source_kind"], "profile-override")
        self.assertEqual(dataset["provenance"]["additional_types"], ["fairy"])
        self.assertEqual(
            dataset["provenance"]["overrides"],
            {
                "dragon>fairy": "0",
                "ghost>steel": "1",
                "steel>fairy": "2",
            },
        )
        fairy = defensive_effectiveness(dataset, ("fairy",))
        self.assertIn("dragon", fairy["0"])
        self.assertIn("steel", fairy["2"])
        steel = defensive_effectiveness(dataset, ("steel",))
        self.assertIn("ghost", steel["1"])

    def test_rejects_invalid_profile_selection_and_overrides(self) -> None:
        with self.assertRaisesRegex(ProfileError, "unknown type chart"):
            build_type_dataset(_profile("gen4_platinum", "missing"))
        with self.assertRaisesRegex(ProfileError, "Unknown type"):
            build_type_dataset(
                _profile(
                    "gen4_platinum",
                    "gen4",
                    overrides={"fairy>dragon": "2"},
                )
            )
        with self.assertRaisesRegex(ProfileError, "Invalid multiplier"):
            build_type_dataset(
                _profile(
                    "gen4_platinum",
                    "gen4",
                    overrides={"fire>grass": "3"},
                )
            )

    def test_rejects_duplicate_incomplete_and_unknown_chart_entries(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "unique"):
            validate_type_chart(
                RegisteredTypeChart(
                    "test",
                    TypeChartFamily(
                        "test",
                        ("normal", "normal"),
                        {("normal", "normal"): "1"},
                    ),
                )
            )
        with self.assertRaisesRegex(DataSourceError, "missing"):
            validate_type_chart(
                RegisteredTypeChart(
                    "test",
                    TypeChartFamily("test", ("normal",), {}),
                )
            )
        with self.assertRaisesRegex(DataSourceError, "unknown"):
            validate_type_chart(
                RegisteredTypeChart(
                    "test",
                    TypeChartFamily(
                        "test",
                        ("normal",),
                        {
                            ("normal", "normal"): "1",
                            ("normal", "missing"): "1",
                        },
                    ),
                )
            )


def _profile(
    engine: str,
    chart: str,
    *,
    additional_types: tuple[str, ...] = (),
    overrides: dict[str, str] | None = None,
) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine=engine,
        base_game="test",
        game_codes=("TEST",),
        rom_versions=(0,),
        hashes=(KnownHash("sha256", "test", "test"),),
        type_chart=TypeChartConfig(
            chart,
            additional_types,
            overrides or {},
        ),
    )


if __name__ == "__main__":
    unittest.main()
