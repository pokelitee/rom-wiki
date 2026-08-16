from __future__ import annotations

import unittest

from romwiki.pipeline.semantics.encounter_identity import (
    EncounterSourceType,
    conditional_encounter_key,
    encounter_route_key,
)


class EncounterIdentityTests(unittest.TestCase):
    def test_builds_catalog_and_public_identities_from_normalized_sources(self) -> None:
        cases = (
            (
                {
                    "source_type": EncounterSourceType.HEADBUTT.value,
                    "header_id": 9,
                },
                "headbutt-009",
                "header-009#headbutt-encounters",
            ),
            (
                {
                    "source_type": EncounterSourceType.HIDDEN_GROTTO.value,
                    "grotto_id": 3,
                    "location": {"header_id": 331},
                },
                "hidden-grotto-03",
                "header-331#hidden-grotto-03",
            ),
            (
                {
                    "source_type": EncounterSourceType.DAILY_SWARM.value,
                    "header_id": 331,
                },
                "daily-swarm-331",
                "header-331#daily-swarm",
            ),
            (
                {
                    "source_type": EncounterSourceType.SAFARI_ZONE.value,
                    "safari_area_id": 4,
                    "area_name": "Rocky Beach",
                },
                "safari-zone-04",
                "safari-zone#rocky-beach",
            ),
        )

        for record, catalog_key, route_key in cases:
            with self.subTest(source_type=record["source_type"]):
                self.assertEqual(conditional_encounter_key(record), catalog_key)
                self.assertEqual(encounter_route_key(record), route_key)

    def test_rejects_a_malformed_catalog_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "header_id must be an integer"):
            conditional_encounter_key(
                {
                    "source_type": EncounterSourceType.DAILY_SWARM.value,
                    "header_id": "331",
                }
            )


if __name__ == "__main__":
    unittest.main()
