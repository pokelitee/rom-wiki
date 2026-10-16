from __future__ import annotations

import unittest

from romwiki.pipeline.semantics.encounter_identity import (
    EncounterSourceType,
    conditional_encounter_key,
    encounter_route_key,
)


class EncounterIdentityTests(unittest.TestCase):
    def test_builds_catalog_and_public_identities_from_normalized_sources(self) -> None:
        # Every conditional source now renders its own page under the
        # encounters section (like Safari Zone already did), so its public
        # route identity is the same bare id as its catalog identity rather
        # than an anchor into the owning location page.
        cases = (
            (
                {
                    "source_type": EncounterSourceType.HEADBUTT.value,
                    "location": {"header_id": 9},
                },
                "headbutt-009",
            ),
            (
                {
                    "source_type": EncounterSourceType.HIDDEN_GROTTO.value,
                    "grotto_id": 3,
                    "location": {"header_id": 331},
                },
                "hidden-grotto-03",
            ),
            (
                {
                    "source_type": EncounterSourceType.DAILY_SWARM.value,
                    "location": {"header_id": 331},
                },
                "daily-swarm-331",
            ),
            (
                {
                    "source_type": EncounterSourceType.SAFARI_ZONE.value,
                    "safari_area_id": 4,
                    "area_name": "Rocky Beach",
                },
                "safari-zone-04",
            ),
        )

        for record, key in cases:
            with self.subTest(source_type=record["source_type"]):
                self.assertEqual(conditional_encounter_key(record), key)
                self.assertEqual(encounter_route_key(record), key)

    def test_rejects_a_malformed_catalog_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "header_id must be an integer"):
            conditional_encounter_key(
                {
                    "source_type": EncounterSourceType.DAILY_SWARM.value,
                    "location": {"header_id": "331"},
                }
            )

    def test_rejects_a_catalog_identifier_missing_its_location(self) -> None:
        # Real extracted headbutt/daily-swarm/grotto records always nest
        # header_id under "location" (extraction/encounters/); a record
        # with a top-level header_id instead is malformed, not a
        # differently-shaped valid record.
        with self.assertRaisesRegex(ValueError, "missing its location"):
            conditional_encounter_key(
                {
                    "source_type": EncounterSourceType.HEADBUTT.value,
                    "header_id": 9,
                }
            )

    def test_rejects_a_malformed_route_identifier_instead_of_falling_back(
        self,
    ) -> None:
        # A route key silently computed from map_index/area_id for a record
        # whose source_type claims to be a conditional source would mismatch
        # the catalog identity conditional_encounter_key computed for the
        # same record -- this must raise instead of silently degrading.
        with self.assertRaisesRegex(ValueError, "header_id must be an integer"):
            encounter_route_key(
                {
                    "source_type": EncounterSourceType.DAILY_SWARM.value,
                    "location": {"header_id": "331"},
                    "area_id": 42,
                }
            )
        with self.assertRaisesRegex(ValueError, "grotto_id must be an integer"):
            encounter_route_key(
                {
                    "source_type": EncounterSourceType.HIDDEN_GROTTO.value,
                    "location": {"header_id": 331},
                    "area_id": 42,
                }
            )
        with self.assertRaisesRegex(ValueError, "header_id must be an integer"):
            encounter_route_key(
                {
                    "source_type": EncounterSourceType.HEADBUTT.value,
                    "location": {"header_id": "331"},
                    "area_id": 42,
                }
            )
        with self.assertRaisesRegex(ValueError, "safari_area_id must be an integer"):
            encounter_route_key(
                {
                    "source_type": EncounterSourceType.SAFARI_ZONE.value,
                    "area_id": 42,
                }
            )


if __name__ == "__main__":
    unittest.main()
