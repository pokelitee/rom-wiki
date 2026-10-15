from __future__ import annotations

import unittest

from romwiki.pipeline.transforms.version_merge import (
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

        merged = merge_version_family_datasets({"black": black, "white": white})
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
            merge_version_family_datasets({"black": black, "white": white})

    def test_preserves_version_specific_reference_prose(self) -> None:
        black = _dataset(
            "pokemon",
            "black-us",
            [
                _pokemon(
                    1,
                    "Bulbasaur",
                    reference={"flavor_text": "Black entry."},
                )
            ],
        )
        white = _dataset(
            "pokemon",
            "white-us",
            [
                _pokemon(
                    1,
                    "Bulbasaur",
                    reference={"flavor_text": "White entry."},
                )
            ],
        )

        record = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ][0]

        self.assertEqual(
            {
                version: reference["flavor_text"]
                for version, reference in record["reference_variants"].items()
            },
            {"black": "Black entry.", "white": "White entry."},
        )

    def test_does_not_variant_identical_reference_prose(self) -> None:
        black = _dataset(
            "pokemon",
            "black-us",
            [_pokemon(1, "Bulbasaur", reference={"flavor_text": "Shared."})],
        )
        white = _dataset(
            "pokemon",
            "white-us",
            [_pokemon(1, "Bulbasaur", reference={"flavor_text": "Shared."})],
        )

        record = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ][0]

        self.assertNotIn("reference_variants", record)

    def test_merges_version_specific_trades_on_an_otherwise_shared_location(
        self,
    ) -> None:
        black = _dataset(
            "locations",
            "black-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [{"trade_id": 0, "nickname": "Lillil"}],
                }
            ],
        )
        white = _dataset(
            "locations",
            "white-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [{"trade_id": 1, "nickname": "Mondo"}],
                }
            ],
        )

        record = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ][0]

        self.assertNotIn("version_variants", record)
        self.assertEqual(
            [(trade["trade_id"], trade["versions"]) for trade in record["npc_trades"]],
            [(0, ["black"]), (1, ["white"])],
        )

    def test_merges_the_same_trade_despite_a_none_vs_missing_field_nuance(
        self,
    ) -> None:
        # The same trade slot, extracted identically in both versions except
        # one side has an explicit `held_item_id: None` where the other
        # simply omits the key -- an extraction-shape nuance the rest of
        # this module tolerates via records_semantically_equal, but which a
        # strict raw dict `==` would treat as two different trades.
        black = _dataset(
            "locations",
            "black-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [
                        {
                            "trade_id": 0,
                            "nickname": "Lillil",
                            "offered_species_id": 1,
                            "held_item_id": None,
                        }
                    ],
                }
            ],
        )
        white = _dataset(
            "locations",
            "white-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [
                        {
                            "trade_id": 0,
                            "nickname": "Lillil",
                            "offered_species_id": 1,
                        }
                    ],
                }
            ],
        )

        record = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ][0]

        self.assertEqual(
            [(trade["trade_id"], trade["versions"]) for trade in record["npc_trades"]],
            [(0, ["black", "white"])],
        )

    def test_keeps_trades_with_the_same_id_separate_when_details_differ(
        self,
    ) -> None:
        # Same trade_id and species, but a different nickname/IVs -- this is
        # a genuinely different trade per version, not a mergeable one. A
        # comparison scoped to only the fields comparisons.py tracks for
        # base-vs-hack diff pages (species/item/formes) would wrongly treat
        # these as the same trade and silently drop one version's nickname
        # and IVs.
        black = _dataset(
            "locations",
            "black-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [
                        {
                            "trade_id": 0,
                            "nickname": "Lillil",
                            "offered_species_id": 1,
                            "ivs": (31, 31, 31, 31, 31, 31),
                        }
                    ],
                }
            ],
        )
        white = _dataset(
            "locations",
            "white-us",
            [
                {
                    "header_id": 23,
                    "name": "Nacrene City",
                    "npc_trades": [
                        {
                            "trade_id": 0,
                            "nickname": "Mondo",
                            "offered_species_id": 1,
                            "ivs": (0, 0, 0, 0, 0, 0),
                        }
                    ],
                }
            ],
        )

        record = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ][0]

        self.assertEqual(
            [(trade["nickname"], trade["versions"]) for trade in record["npc_trades"]],
            [("Lillil", ["black"]), ("Mondo", ["white"])],
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

    def test_keeps_version_specific_daily_swarm_species(self) -> None:
        shared = {
            "area_id": 194,
            "active": True,
            "name": "Route 6",
            "source_type": "daily-swarm",
            "location": {"header_id": 331, "name": "Route 6"},
            "minimum_level": 40,
            "maximum_level": 55,
        }
        black = _dataset(
            "wild_encounters",
            "black-2-us",
            [{**shared, "species_id": 311, "pokemon": {"name": "Plusle"}}],
        )
        white = _dataset(
            "wild_encounters",
            "white-2-us",
            [{**shared, "species_id": 312, "pokemon": {"name": "Minun"}}],
        )

        record = merge_version_family_datasets({"black-2": black, "white-2": white})[
            "records"
        ][0]

        self.assertEqual(record["version_variants"]["black-2"]["species_id"], 311)
        self.assertEqual(record["version_variants"]["white-2"]["species_id"], 312)

    def test_merges_daily_swarms_by_location_instead_of_table_position(self) -> None:
        def swarm(area_id: int, header_id: int, species_id: int) -> dict:
            return {
                "area_id": area_id,
                "active": True,
                "name": f"Location {header_id}",
                "source_type": "daily-swarm",
                "location": {
                    "header_id": header_id,
                    "name": f"Location {header_id}",
                },
                "species_id": species_id,
                "pokemon": {"name": f"Species {species_id}"},
                "minimum_level": 40,
                "maximum_level": 55,
            }

        black = _dataset(
            "wild_encounters",
            "black",
            [swarm(205, 370, 1), swarm(206, 376, 2)],
        )
        white = _dataset(
            "wild_encounters",
            "white",
            [swarm(205, 376, 3), swarm(206, 378, 4)],
        )

        records = merge_version_family_datasets({"black": black, "white": white})[
            "records"
        ]
        shrine = next(
            record for record in records if record["location"]["header_id"] == 376
        )

        self.assertEqual(shrine["versions"], ["black", "white"])
        self.assertEqual(
            {
                version: variant["species_id"]
                for version, variant in shrine["version_variants"].items()
            },
            {"black": 2, "white": 3},
        )
        self.assertEqual(len(records), 3)

    def test_rejects_mismatched_dataset_kinds(self) -> None:
        black = _dataset("pokemon", "black-us", [_pokemon(1, "Bulbasaur")])
        white = _dataset("items", "white-us", [])

        with self.assertRaises(DataSourceError):
            merge_version_family_datasets({"black": black, "white": white})

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
            merge_version_family_datasets({"black": black, "white": white})

    def test_keeps_matching_semantic_formats(self) -> None:
        black = {
            **_dataset("locations", "black-us", []),
            "location_format": "event-map",
        }
        white = {
            **_dataset("locations", "white-us", []),
            "location_format": "event-map",
        }

        merged = merge_version_family_datasets({"black": black, "white": white})

        self.assertEqual(merged["location_format"], "event-map")

    def test_rejects_mismatched_semantic_formats(self) -> None:
        for field in ("encounter_format", "location_format"):
            with self.subTest(field=field):
                kind = "wild_encounters" if field == "encounter_format" else "locations"
                black = {**_dataset(kind, "black-us", []), field: "conditional"}
                white = {**_dataset(kind, "white-us", []), field: "seasonal"}

                with self.assertRaisesRegex(DataSourceError, "semantic formats"):
                    merge_version_family_datasets({"black": black, "white": white})

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

        merged = merge_version_family_comparisons(
            {"blaze-black": black, "volt-white": white}
        )
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

    def test_keeps_every_versions_differing_value_for_the_same_changed_field(
        self,
    ) -> None:
        # Both versions change the same field, but to different values --
        # the flat `changes` list must not silently keep only one version's
        # before/after and drop the other.
        black = _comparison(
            "items",
            "blaze-black",
            "black-us",
            [
                {
                    "kind": "items",
                    "key": 1,
                    "status": "changed",
                    "label": "Item 1",
                    "slug": "item-1",
                    "detail_available": True,
                    "changes": [
                        {"field": "price", "label": "Price", "before": 10, "after": 20}
                    ],
                }
            ],
        )
        white = _comparison(
            "items",
            "volt-white",
            "white-us",
            [
                {
                    "kind": "items",
                    "key": 1,
                    "status": "changed",
                    "label": "Item 1",
                    "slug": "item-1",
                    "detail_available": True,
                    "changes": [
                        {"field": "price", "label": "Price", "before": 10, "after": 15}
                    ],
                }
            ],
        )

        merged = merge_version_family_comparisons(
            {"blaze-black": black, "volt-white": white}
        )
        record = merged["records"][0]

        self.assertEqual(
            [(change["label"], change["after"]) for change in record["changes"]],
            [("Price (blaze-black)", 20), ("Price (volt-white)", 15)],
        )

    def test_rejects_mismatched_comparison_kinds(self) -> None:
        with self.assertRaises(DataSourceError):
            merge_version_family_comparisons(
                {
                    "a": _comparison("items", "a", "base-a", []),
                    "b": _comparison("moves", "b", "base-b", []),
                }
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
