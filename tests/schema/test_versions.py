from __future__ import annotations

import unittest

from romwiki.schema import versions


class SchemaVersionTests(unittest.TestCase):
    def test_all_schema_versions_are_positive_integers(self) -> None:
        declared = {
            name: value
            for name, value in vars(versions).items()
            if name.endswith("_SCHEMA_VERSION")
        }

        self.assertTrue(declared)
        self.assertTrue(
            all(isinstance(value, int) and value > 0 for value in declared.values())
        )

    def test_raw_cache_contracts_have_independent_versions(self) -> None:
        self.assertEqual(
            set(versions.RAW_SCHEMA_VERSION_BY_CACHE_KEY),
            {
                "pokemon/personal",
                "pokemon/learnsets",
                "pokemon/egg-moves",
                "pokemon/evolutions",
                "machines/raw",
                "tutors/raw",
                "moves/raw",
                "encounters/raw",
                "trainers/raw",
                "locations/raw",
                "items/raw",
            },
        )


if __name__ == "__main__":
    unittest.main()
