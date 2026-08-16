from __future__ import annotations

import unittest

from romwiki.schema import dataset_envelope, validate_dataset_envelope
from romwiki.util.errors import DataSourceError


class DatasetEnvelopeTests(unittest.TestCase):
    def test_constructor_sets_required_fields_and_record_count(self) -> None:
        dataset = dataset_envelope(
            schema_version=1,
            game="test-game",
            engine="test-engine",
            dataset="moves",
            source={"rom_sha256": "abc"},
            records=[{"move_id": 1}],
        )

        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(dataset["records"], [{"move_id": 1}])

    def test_accepts_the_shared_dataset_envelope(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "engine": "test-engine",
            "dataset": "moves",
            "record_count": 1,
            "source": {"rom_sha256": "abc"},
            "records": [{"move_id": 1}],
        }

        self.assertIs(validate_dataset_envelope(dataset, context="test"), dataset)

    def test_accepts_an_envelope_with_no_records_list(self) -> None:
        # A handful of dataset kinds (e.g. pickup's) report one logical
        # record through kind-specific fields instead of a `records` list --
        # validation must not require a field that's legitimately absent.
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "engine": "test-engine",
            "dataset": "pickup",
            "record_count": 1,
            "source": {"rom_sha256": "abc"},
            "tables": {},
        }

        self.assertIs(validate_dataset_envelope(dataset, context="test"), dataset)

    def test_rejects_a_record_count_that_does_not_match_the_records_list(
        self,
    ) -> None:
        with self.assertRaisesRegex(DataSourceError, "record_count \\(2\\)"):
            validate_dataset_envelope(
                {
                    "schema_version": 1,
                    "game": "test-game",
                    "engine": "test-engine",
                    "dataset": "moves",
                    "record_count": 2,
                    "source": {},
                    "records": [{"move_id": 1}],
                },
                context="test",
            )

    def test_rejects_a_records_field_that_is_not_a_list(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "envelope fields: records"):
            validate_dataset_envelope(
                {
                    "schema_version": 1,
                    "game": "test-game",
                    "engine": "test-engine",
                    "dataset": "moves",
                    "record_count": 1,
                    "source": {},
                    "records": "not-a-list",
                },
                context="test",
            )

    def test_rejects_an_incomplete_dataset_envelope(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "engine, record_count"):
            validate_dataset_envelope(
                {
                    "schema_version": 1,
                    "game": "test-game",
                    "dataset": "moves",
                    "source": {},
                },
                context="test",
            )


if __name__ == "__main__":
    unittest.main()
