from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from romwiki.pipeline.comparisons import (
    RECORD_KEY_FIELDS,
    comparison_by_key,
    records_by_key,
    records_semantically_equal,
)
from romwiki.util.errors import DataSourceError

# These dataset renderers present complete same-key variants. Other dataset
# kinds may still contain version-exclusive records, but a same-key difference
# must not silently fall back to the first version's value.
VERSION_VARIANT_DATASETS = frozenset({"items", "wild_encounters"})


def merge_version_datasets(
    primary: dict[str, Any],
    primary_version: str,
    secondary: dict[str, Any],
    secondary_version: str,
) -> dict[str, Any]:
    """Backward-compatible two-version wrapper."""
    return merge_version_family_datasets(
        {
            primary_version: primary,
            secondary_version: secondary,
        }
    )


def merge_version_family_datasets(
    datasets: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Combine two or more co-equal sibling-version datasets."""
    _validate_family_size(datasets)
    versions = tuple(datasets)
    first_dataset = datasets[versions[0]]
    kind = first_dataset.get("dataset")
    if kind not in RECORD_KEY_FIELDS or any(
        dataset.get("dataset") != kind for dataset in datasets.values()
    ):
        raise DataSourceError(
            "Version-family datasets must have the same supported kind"
        )
    features = first_dataset.get("features", [])
    if any(dataset.get("features", []) != features for dataset in datasets.values()):
        raise DataSourceError(
            "Version-family datasets must have matching feature capabilities"
        )

    key_name = RECORD_KEY_FIELDS[kind]
    records = {
        version: records_by_key(dataset, key_name)
        for version, dataset in datasets.items()
    }
    keys = set().union(*(values.keys() for values in records.values()))
    merged_records = []
    for key in sorted(keys, key=_record_sort_key):
        variants = {
            version: records[version][key]
            for version in versions
            if key in records[version]
        }
        record = dict(next(iter(variants.values())))
        record["versions"] = list(variants)
        if not _all_semantically_equal(kind, variants.values()):
            if kind not in VERSION_VARIANT_DATASETS:
                raise DataSourceError(
                    f"{kind} record {key!r} differs across versions, but its "
                    "renderer does not support complete version variants"
                )
            record["version_variants"] = variants
        merged_records.append(record)

    return {
        **first_dataset,
        "game": "-".join(versions),
        "source": {
            version: dataset.get("source") for version, dataset in datasets.items()
        },
        "record_count": len(merged_records),
        "records": merged_records,
    }


def merge_version_comparisons(
    primary: dict[str, Any],
    primary_version: str,
    secondary: dict[str, Any],
    secondary_version: str,
) -> dict[str, Any]:
    """Backward-compatible two-version wrapper."""
    return merge_version_family_comparisons(
        {
            primary_version: primary,
            secondary_version: secondary,
        }
    )


def merge_version_family_comparisons(
    comparisons: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Combine hack-vs-base comparisons for a sibling-version family."""
    _validate_family_size(comparisons)
    versions = tuple(comparisons)
    first_comparison = comparisons[versions[0]]
    kind = first_comparison.get("kind")
    if (
        kind not in RECORD_KEY_FIELDS
        or first_comparison.get("dataset") != f"{kind}_comparison"
        or any(
            comparison.get("kind") != kind
            or comparison.get("dataset") != f"{kind}_comparison"
            for comparison in comparisons.values()
        )
    ):
        raise DataSourceError(
            "Version-family comparisons must have the same supported kind"
        )
    coverage = first_comparison.get("coverage")
    if any(
        comparison.get("coverage") != coverage for comparison in comparisons.values()
    ):
        raise DataSourceError("Version-family comparisons must have matching coverage")

    records = {
        version: comparison_by_key(comparison)
        for version, comparison in comparisons.items()
    }
    keys = set().union(*(values.keys() for values in records.values()))
    merged_records = []
    counts = dict.fromkeys(("unchanged", "changed", "added", "removed"), 0)
    for key in sorted(keys, key=_record_sort_key):
        entries = {
            version: records[version][key]
            for version in versions
            if key in records[version]
        }
        record = dict(next(iter(entries.values())))
        record["versions"] = list(entries)
        if len(entries) != len(versions) or not _all_equal(entries.values()):
            version_comparisons = {
                version: {
                    **entry,
                    "baseline": comparisons[version].get("baseline"),
                }
                for version, entry in entries.items()
            }
            record["version_comparisons"] = version_comparisons
            record["status"] = _combined_status(
                {entry["status"] for entry in entries.values()}
            )
            record["changes"] = _combined_changes(entries.values())
            record["detail_available"] = any(
                entry.get("detail_available") for entry in entries.values()
            )
        counts[record["status"]] += 1
        merged_records.append(record)

    return {
        **first_comparison,
        "game": "-".join(versions),
        "baseline": " / ".join(
            str(comparison.get("baseline")) for comparison in comparisons.values()
        ),
        "source": {
            version: comparison.get("source")
            for version, comparison in comparisons.items()
        },
        "counts": counts,
        "records": merged_records,
    }


def _validate_family_size(values: Mapping[str, object]) -> None:
    if len(values) < 2:
        raise DataSourceError("A version family requires at least two versions")
    if any(not version for version in values):
        raise DataSourceError("Version labels must be non-empty")


def _all_equal(values: Iterable[object]) -> bool:
    entries = iter(values)
    first = next(entries)
    return all(entry == first for entry in entries)


def _all_semantically_equal(kind: str, values: Iterable[dict[str, Any]]) -> bool:
    entries = iter(values)
    first = next(entries)
    return all(records_semantically_equal(kind, first, entry) for entry in entries)


def _record_sort_key(value: object) -> tuple[str, object]:
    if isinstance(value, (int, float, str)):
        return type(value).__name__, value
    return type(value).__name__, repr(value)


def _combined_status(statuses: set[str]) -> str:
    for status in ("changed", "added", "removed", "unchanged"):
        if status in statuses:
            return status
    raise DataSourceError("Version comparison has no supported status")


def _combined_changes(
    entries: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    changes = []
    fields = set()
    for entry in entries:
        for change in entry.get("changes", []):
            field = change.get("field", change.get("label"))
            if field not in fields:
                fields.add(field)
                changes.append(change)
    return changes
