from __future__ import annotations

import types
import unittest
from dataclasses import replace

from romwiki.engines.profile_contracts import EngineProfileContract
from romwiki.engines.registry import (
    GEN5_B2W2_ENGINE,
    get_engine,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.build.sections import enabled_dataset_kinds
from romwiki.util.errors import ProfileError

_PARTIAL_ENGINE = "partial_test_engine"


class DatasetSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        source = get_engine(GEN5_B2W2_ENGINE)
        register_engine(
            _PARTIAL_ENGINE,
            replace(
                source,
                pickup=types.SimpleNamespace(),
                tutors=types.SimpleNamespace(),
                static_encounters=types.SimpleNamespace(),
                formats=replace(
                    source.formats,
                    pickup="none",
                    tutors="none",
                    fossils="none",
                    static_encounters="none",
                ),
                dataset_kinds=frozenset({"pokemon", "abilities"}),
                required_dataset_kinds=frozenset({"pokemon"}),
                profile_contract=EngineProfileContract(
                    required_layout=frozenset({"personal"}),
                    optional_layout=frozenset({"moves", "encounters"}),
                    reject_unknown=True,
                ),
            ),
        )

    def tearDown(self) -> None:
        unregister_engine(_PARTIAL_ENGINE)

    def test_partial_engine_enables_only_declared_sections(self) -> None:
        profile = types.SimpleNamespace(
            id="future-game",
            engine=_PARTIAL_ENGINE,
            layout={
                "personal": "personal.bin",
                "moves": "unused-moves.bin",
                "encounters": "unused-encounters.bin",
            },
        )

        self.assertEqual(
            enabled_dataset_kinds(profile),
            ("pokemon", "abilities"),
        )

    def test_partial_engine_still_requires_its_vertical_slice(self) -> None:
        profile = types.SimpleNamespace(
            id="future-game",
            engine=_PARTIAL_ENGINE,
            layout={},
        )

        with self.assertRaisesRegex(
            ProfileError, "future-game.*missing required layout: personal"
        ):
            enabled_dataset_kinds(profile)

    def test_profile_contract_rejects_unknown_engine_keys(self) -> None:
        profile = types.SimpleNamespace(
            id="future-game",
            engine=_PARTIAL_ENGINE,
            layout={"personal": "personal.bin", "personl": "typo.bin"},
            parameters={},
        )

        with self.assertRaisesRegex(ProfileError, "unsupported layout: personl"):
            enabled_dataset_kinds(profile)


if __name__ == "__main__":
    unittest.main()
