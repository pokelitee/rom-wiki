from __future__ import annotations

import unittest

from romwiki.pipeline.version_merge import merge_version_datasets
from romwiki.util.errors import DataSourceError


class VersionMergeTests(unittest.TestCase):
    def test_tags_shared_and_exclusive_records(self) -> None:
        black = _dataset(
            "pokemon",
            "black-us",
            [
                _pokemon(1, "Bulbasaur"),
                _pokemon(644, "Zekrom"),
            ],
        )
        white = _dataset(
            "pokemon",
            "white-us",
            [
                _pokemon(1, "Bulbasaur"),
                _pokemon(643, "Reshiram"),
            ],
        )

        merged = merge_version_datasets(black, "black", white, "white")
        records = {record["member"]: record for record in merged["records"]}

        self.assertEqual(merged["dataset"], "pokemon")
        self.assertEqual(merged["record_count"], 3)
        self.assertEqual(records[1]["versions"], ["black", "white"])
        self.assertEqual(records[644]["versions"], ["black"])
        self.assertEqual(records[643]["versions"], ["white"])
        self.assertNotIn("version_variants", records[1])

    def test_flags_records_that_differ_between_versions(self) -> None:
        black = _dataset("pokemon", "black-us", [_pokemon(1, "Bulbasaur", power=40)])
        white = _dataset("pokemon", "white-us", [_pokemon(1, "Bulbasaur", power=41)])

        merged = merge_version_datasets(black, "black", white, "white")
        record = merged["records"][0]

        self.assertEqual(record["versions"], ["black", "white"])
        self.assertIn("version_variants", record)
        self.assertEqual(record["version_variants"]["black"]["power"], 40)
        self.assertEqual(record["version_variants"]["white"]["power"], 41)

    def test_rejects_mismatched_dataset_kinds(self) -> None:
        black = _dataset("pokemon", "black-us", [_pokemon(1, "Bulbasaur")])
        white = _dataset("items", "white-us", [])

        with self.assertRaises(DataSourceError):
            merge_version_datasets(black, "black", white, "white")


def _dataset(kind: str, game: str, records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "dataset": kind,
        "game": game,
        "source": {"rom_sha256": game},
        "records": records,
    }


def _pokemon(member: int, name: str, **overrides: object) -> dict:
    record = {
        "member": member,
        "national_dex_id": member,
        "name": name,
        "slug": name.lower(),
        "public": True,
    }
    record.update(overrides)
    return record


if __name__ == "__main__":
    unittest.main()
