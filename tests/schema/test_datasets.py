from __future__ import annotations

import unittest

from romwiki.schema import validate_dataset_envelope
from romwiki.util.errors import DataSourceError


class DatasetEnvelopeTests(unittest.TestCase):
    def test_accepts_the_shared_dataset_envelope(self) -> None:
        dataset = {
            "schema_version": 1,
            "game": "test-game",
            "engine": "test-engine",
            "dataset": "moves",
            "record_count": 1,
            "source": {"rom_sha256": "abc"},
            "records": [],
        }

        self.assertIs(
            validate_dataset_envelope(dataset, context="test"), dataset
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
