from __future__ import annotations

import unittest

from romwiki.pipeline.version_merge import (
    merge_version_comparisons,
    merge_version_datasets,
    merge_version_family_comparisons,
    merge_version_family_datasets,
)
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

    def test_rejects_differing_records_without_variant_renderer(self) -> None:
        black = _dataset("moves", "black-us", [_move(1, 40)])
        white = _dataset("moves", "white-us", [_move(1, 41)])

        with self.assertRaisesRegex(DataSourceError, "does not support"):
            merge_version_datasets(black, "black", white, "white")

    def test_merges_version_specific_trades_on_an_otherwise_shared_location(
        self,
    ) -> None:
        black = _dataset(
            "locations", "black-us",
            [{"header_id": 23, "name": "Nacrene City", "npc_trades": [
                {"trade_id": 0, "nickname": "Lillil"}
            ]}],
        )
        white = _dataset(
            "locations", "white-us",
            [{"header_id": 23, "name": "Nacrene City", "npc_trades": [
                {"trade_id": 1, "nickname": "Mondo"}
            ]}],
        )

        record = merge_version_datasets(black, "black", white, "white")["records"][0]

        self.assertNotIn("version_variants", record)
        self.assertEqual(
            [(trade["trade_id"], trade["versions"]) for trade in record["npc_trades"]],
            [(0, ["black"]), (1, ["white"])],
        )

    def test_merges_renderable_variants_for_three_versions(self) -> None:
        datasets = {
            "red": _dataset("items", "red", [_item(1, 100)]),
            "blue": _dataset("items", "blue", [_item(1, 200)]),
            "yellow": _dataset("items", "yellow", [_item(1, 300)]),
        }

        merged = merge_version_family_datasets(datasets)
        record = merged["records"][0]

        self.assertEqual(record["versions"], ["red", "blue", "yellow"])
        self.assertEqual(
            {
                version: value["price"]
                for version, value in record["version_variants"].items()
            },
            {"red": 100, "blue": 200, "yellow": 300},
        )

    def test_rejects_mismatched_dataset_kinds(self) -> None:
        black = _dataset("pokemon", "black-us", [_pokemon(1, "Bulbasaur")])
        white = _dataset("items", "white-us", [])

        with self.assertRaises(DataSourceError):
            merge_version_datasets(black, "black", white, "white")

    def test_rejects_mismatched_feature_contracts(self) -> None:
        black = {
            **_dataset("pokemon", "black-us", [_pokemon(1, "Bulbasaur")]),
            "features": ["victory-items"],
        }
        white = {
            **_dataset("pokemon", "white-us", [_pokemon(1, "Bulbasaur")]),
            "features": [],
        }

        with self.assertRaisesRegex(DataSourceError, "feature capabilities"):
            merge_version_datasets(black, "black", white, "white")

    def test_merges_shared_and_version_specific_comparisons(self) -> None:
        black = _comparison(
            "items",
            "blaze-black",
            "black-us",
            [
                _comparison_record(1, "changed", ["price"]),
                _comparison_record(2, "changed", ["trades"]),
            ],
        )
        white = _comparison(
            "items",
            "volt-white",
            "white-us",
            [
                _comparison_record(1, "changed", ["price"]),
                _comparison_record(2, "unchanged", []),
            ],
        )

        merged = merge_version_comparisons(black, "blaze-black", white, "volt-white")
        records = {record["key"]: record for record in merged["records"]}

        self.assertEqual(
            merged["counts"],
            {"unchanged": 0, "changed": 2, "added": 0, "removed": 0},
        )
        self.assertNotIn("version_comparisons", records[1])
        self.assertEqual(
            set(records[2]["version_comparisons"]),
            {"blaze-black", "volt-white"},
        )
        self.assertEqual(
            records[2]["version_comparisons"]["volt-white"]["baseline"],
            "white-us",
        )

    def test_rejects_mismatched_comparison_kinds(self) -> None:
        with self.assertRaises(DataSourceError):
            merge_version_comparisons(
                _comparison("items", "a", "base-a", []),
                "a",
                _comparison("moves", "b", "base-b", []),
                "b",
            )

    def test_single_version_comparison_row_keeps_its_baseline(self) -> None:
        merged = merge_version_family_comparisons(
            {
                "red-hack": _comparison(
                    "items",
                    "red-hack",
                    "red",
                    [_comparison_record(1, "added", ["price"])],
                ),
                "blue-hack": _comparison("items", "blue-hack", "blue", []),
                "yellow-hack": _comparison("items", "yellow-hack", "yellow", []),
            }
        )

        record = merged["records"][0]
        self.assertEqual(record["versions"], ["red-hack"])
        self.assertEqual(record["version_comparisons"]["red-hack"]["baseline"], "red")


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


def _item(item_id: int, price: int) -> dict:
    return {
        "item_id": item_id,
        "name": f"Item {item_id}",
        "slug": f"item-{item_id}",
        "price": price,
    }


def _move(move_id: int, power: int) -> dict:
    return {
        "move_id": move_id,
        "name": f"Move {move_id}",
        "slug": f"move-{move_id}",
        "power": power,
    }


def _comparison(
    kind: str,
    game: str,
    baseline: str,
    records: list[dict],
) -> dict:
    return {
        "schema_version": 1,
        "dataset": f"{kind}_comparison",
        "kind": kind,
        "game": game,
        "baseline": baseline,
        "source": {},
        "coverage": ["price", "trades"] if kind == "items" else ["power"],
        "counts": {},
        "records": records,
    }


def _comparison_record(key: int, status: str, changed_fields: list[str]) -> dict:
    return {
        "kind": "items",
        "key": key,
        "status": status,
        "label": f"Item {key}",
        "slug": f"item-{key}",
        "detail_available": True,
        "changes": [
            {
                "field": field,
                "label": field.title(),
                "before": 1,
                "after": 2,
            }
            for field in changed_fields
        ],
    }


if __name__ == "__main__":
    unittest.main()
