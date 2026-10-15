from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.locations import enrich_location_dataset
from romwiki.schema.versions import LOCATIONS_ENRICHED_SCHEMA_VERSION


class LocationEnrichmentTests(unittest.TestCase):
    def test_publishes_the_engine_location_format(self) -> None:
        raw = {
            "schema_version": 1,
            "game": "test",
            "engine": "gen4_hgss",
            "dataset": "locations",
            "record_count": 0,
            "source": {},
            "records": [],
        }

        enriched = enrich_location_dataset(raw)

        self.assertEqual(enriched["location_format"], "encounter-map")
        self.assertEqual(enriched["schema_version"], LOCATIONS_ENRICHED_SCHEMA_VERSION)
        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(
            enrich_location_dataset({**raw, "engine": "gen4_platinum"})[
                "location_format"
            ],
            "event-map",
        )


if __name__ == "__main__":
    unittest.main()
