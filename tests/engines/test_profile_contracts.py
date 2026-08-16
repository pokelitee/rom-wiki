from __future__ import annotations

import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from romwiki.engines.profile_contracts import EngineProfileContract
from romwiki.util.errors import ProfileError


@dataclass(frozen=True, slots=True)
class _Profile:
    id: str
    layout: dict[str, str]
    parameters: dict[str, object]


class EngineProfileContractTests(unittest.TestCase):
    def test_accepts_a_complete_profile(self) -> None:
        contract = EngineProfileContract(
            required_layout=frozenset({"personal"}),
            required_parameters=frozenset({"pickup_overlay_id"}),
        )
        profile = _Profile(
            id="test-game",
            layout={"personal": "a/0/0/0"},
            parameters={"pickup_overlay_id": 78},
        )

        contract.validate(profile)  # does not raise

    def test_rejects_missing_required_layout(self) -> None:
        contract = EngineProfileContract(required_layout=frozenset({"personal"}))
        profile = _Profile(id="test-game", layout={}, parameters={})

        with self.assertRaisesRegex(ProfileError, "missing required layout: personal"):
            contract.validate(profile)

    def test_rejects_missing_required_parameters(self) -> None:
        contract = EngineProfileContract(
            required_parameters=frozenset({"pickup_overlay_id"})
        )
        profile = _Profile(id="test-game", layout={}, parameters={})

        with self.assertRaisesRegex(
            ProfileError, "missing required parameters: pickup_overlay_id"
        ):
            contract.validate(profile)

    def test_rejects_unknown_layout_or_parameters_when_configured(self) -> None:
        contract = EngineProfileContract(
            required_layout=frozenset({"personal"}), reject_unknown=True
        )
        profile = _Profile(
            id="test-game",
            layout={"personal": "a/0/0/0", "unknown_section": "a/1/1/1"},
            parameters={"unknown_parameter": 1},
        )

        with self.assertRaisesRegex(ProfileError, "unsupported layout"):
            contract.validate(profile)

    def test_rejects_a_string_value_for_an_offset_parameter(self) -> None:
        # A TOML author accidentally quoting a number (e.g.
        # `pickup_overlay_id = "78"`) must fail loudly here, at profile
        # validation, rather than surfacing later as an unclear TypeError
        # deep inside extraction code that indexes with the raw value.
        contract = EngineProfileContract(
            required_parameters=frozenset({"pickup_overlay_id"})
        )
        profile = _Profile(
            id="test-game",
            layout={},
            parameters={"pickup_overlay_id": "78"},
        )

        with self.assertRaisesRegex(
            ProfileError, "non-integer values for parameters: pickup_overlay_id"
        ):
            contract.validate(profile)

    def test_rejects_a_bool_value_for_a_count_parameter(self) -> None:
        # isinstance(True, int) is True in Python -- must be excluded
        # explicitly, or a stray `true`/`false` in TOML would pass as 1/0.
        contract = EngineProfileContract(required_parameters=frozenset({"tutor_count"}))
        profile = _Profile(id="test-game", layout={}, parameters={"tutor_count": True})

        with self.assertRaisesRegex(ProfileError, "non-integer values"):
            contract.validate(profile)

    def test_does_not_type_check_parameters_outside_the_offset_count_id_convention(
        self,
    ) -> None:
        # Locators, contract IDs, and exclusion lists are legitimately
        # non-int; only the offset/count/id naming convention is enforced.
        contract = EngineProfileContract(
            required_parameters=frozenset(
                {"shop_catalog_locator", "trainer_variant_contract", "special_tutors"}
            )
        )
        profile = _Profile(
            id="test-game",
            layout={},
            parameters={
                "shop_catalog_locator": "deadbeef",
                "trainer_variant_contract": "hgss-retail-v1",
                "special_tutors": [{"script_member": 1}],
            },
        )

        contract.validate(profile)  # does not raise

    def test_rejects_a_non_mapping_layout_or_parameters(self) -> None:
        contract = EngineProfileContract()
        profile = SimpleNamespace(id="test-game", layout=["not", "a", "mapping"])

        with self.assertRaisesRegex(ProfileError, "invalid layout entries"):
            contract.validate(profile)


if __name__ == "__main__":
    unittest.main()
