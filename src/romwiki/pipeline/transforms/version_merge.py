from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from romwiki.pipeline.transforms.comparisons import (
    RECORD_KEY_FIELDS,
    comparison_by_key,
    records_by_identity,
    records_semantically_equal,
)
from romwiki.util.errors import DataSourceError

# These dataset renderers present complete same-key variants. Other dataset
# kinds may still contain version-exclusive records, but a same-key difference
# must not silently fall back to the first version's value.
VERSION_VARIANT_DATASETS = frozenset({"items", "trades", "wild_encounters"})


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
    for format_field in ("encounter_format", "location_format"):
        semantic_format = first_dataset.get(format_field)
        if any(
            dataset.get(format_field) != semantic_format
            for dataset in datasets.values()
        ):
            raise DataSourceError(
                "Version-family datasets must have matching semantic formats"
            )
    trainer_variant_support = first_dataset.get("trainer_variant_support")
    if kind == "trainers" and any(
        dataset.get("trainer_variant_support") != trainer_variant_support
        for dataset in datasets.values()
    ):
        raise DataSourceError(
            "Version-family trainer datasets must have matching variant capabilities"
        )

    records = {
        version: records_by_identity(dataset, kind)
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
        reference_variants = {
            version: value.get("reference") for version, value in variants.items()
        }
        if not _reference_prose_equal(reference_variants.values()):
            record["reference_variants"] = reference_variants
        locations_with_versioned_trades = (
            _merge_location_trade_variants(variants) if kind == "locations" else None
        )
        if locations_with_versioned_trades is not None:
            record = locations_with_versioned_trades
            record["versions"] = list(variants)
        elif not _all_semantically_equal(kind, variants.values()):
            if kind not in VERSION_VARIANT_DATASETS:
                raise DataSourceError(
                    f"{kind} record {key!r} differs across versions, but its "
                    "renderer does not support complete version variants"
                )
            record["version_variants"] = variants
        merged_records.append(record)

    merged = {
        **first_dataset,
        "game": "-".join(versions),
        "source": {
            version: dataset.get("source") for version, dataset in datasets.items()
        },
        "record_count": len(merged_records),
        "records": merged_records,
    }
    if kind == "trainers":
        merged["battle_families"] = _merge_trainer_battle_families(datasets)
    return merged


def _reference_prose_equal(references: Iterable[object]) -> bool:
    fields = ("short_effect", "effect", "flavor_text")
    values = iter(references)
    first = next(values)

    def prose(reference: object) -> tuple[object, ...]:
        if not isinstance(reference, Mapping):
            return (None,) * len(fields)
        return tuple(reference.get(field) for field in fields)

    expected = prose(first)
    return all(prose(reference) == expected for reference in values)


def _merge_trainer_battle_families(
    datasets: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge rule provenance while keeping sibling-ROM and battle axes separate."""
    versions = tuple(datasets)
    first = datasets[versions[0]].get("battle_families", [])
    if not isinstance(first, list):
        raise DataSourceError("Trainer battle families must be a list")
    first_shape = [_family_without_provenance(family) for family in first]
    for version in versions[1:]:
        families = datasets[version].get("battle_families", [])
        if (
            not isinstance(families, list)
            or [_family_without_provenance(family) for family in families]
            != first_shape
        ):
            raise DataSourceError(
                "Sibling-version trainer battle families differ; explicit "
                "sibling-version conditions are required"
            )
    result = []
    for index, family in enumerate(first):
        references = [
            f"{version}={datasets[version]['battle_families'][index]['provenance']['reference']}"
            for version in versions
        ]
        result.append(
            {
                **family,
                "provenance": {
                    **family["provenance"],
                    "reference": "; ".join(references),
                },
            }
        )
    return result


def _family_without_provenance(family: object) -> object:
    if not isinstance(family, dict):
        return family
    return {key: value for key, value in family.items() if key != "provenance"}


# Every NpcTrade field (schema/trades.py) except `trade_id` (compared
# separately, as identity) and `provenance` (legitimately differs per
# ROM/version -- it's where the record was extracted from, not what it is).
_TRADE_IDENTITY_FIELDS = (
    "nickname",
    "ot_name",
    "ot_id",
    "offered_species_id",
    "offered_forme_id",
    "requested_species_id",
    "held_item_id",
    "ivs",
    "interaction",
)


def _same_trade(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Compare two trade records for identity across sibling versions.

    Field-by-field with `.get()` so a value simply being absent compares
    equal to it being explicitly `None` (an extraction-shape nuance the rest
    of this module tolerates via `records_semantically_equal`) -- but
    unlike that helper, every trade-identifying field is compared, not just
    the narrower subset `comparisons.py`'s `_FIELDS["trades"]` tracks for
    base-vs-hack diff pages. A trade differing only in nickname, OT info, or
    IVs is a different trade, not an extraction quirk.
    """
    return all(
        first.get(field) == second.get(field) for field in _TRADE_IDENTITY_FIELDS
    )


def _merge_location_trade_variants(
    variants: Mapping[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Merge version-specific nested trades on an otherwise shared map."""
    without_trades = []
    for value in variants.values():
        candidate = dict(value)
        candidate["npc_trades"] = []
        without_trades.append(candidate)
    if not _all_semantically_equal("locations", without_trades):
        return None

    merged = dict(next(iter(variants.values())))
    trades: list[dict[str, Any]] = []
    for version, value in variants.items():
        for trade in value.get("npc_trades", []):
            existing = next(
                (
                    candidate
                    for candidate in trades
                    if candidate["trade_id"] == trade["trade_id"]
                    and _same_trade(candidate, trade)
                ),
                None,
            )
            if existing is None:
                trades.append({**trade, "versions": [version]})
            else:
                existing["versions"].append(version)
    trades.sort(key=lambda trade: (trade["trade_id"], trade["versions"]))
    merged["npc_trades"] = trades
    return merged


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
            record["changes"] = _combined_changes(entries.items())
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
    entries: Iterable[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Combine each version's field-level changes into one flat list.

    A field that changed to the same value in every version that touched it
    keeps a single entry. A field that changed to a *different* value in at
    least one version keeps one entry per distinct value, each labeled with
    the version(s) it came from -- rather than silently keeping only the
    first version's value and discarding the differing ones. The full detail
    also lives in `version_comparisons`, but the flat `changes` list a
    renderer reads directly should not misrepresent one version's value as
    universal.
    """
    by_field: dict[Any, list[tuple[str, dict[str, Any]]]] = {}
    for version, entry in entries:
        for change in entry.get("changes", []):
            field = change.get("field", change.get("label"))
            by_field.setdefault(field, []).append((version, change))
    changes = []
    for versioned_changes in by_field.values():
        changes.extend(_combine_field_variants(versioned_changes))
    return changes


def _combine_field_variants(
    versioned_changes: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    variants: list[tuple[Any, Any, dict[str, Any], list[str]]] = []
    for version, change in versioned_changes:
        before, after = change.get("before"), change.get("after")
        for existing_before, existing_after, _, versions in variants:
            if existing_before == before and existing_after == after:
                versions.append(version)
                break
        else:
            variants.append((before, after, change, [version]))
    if len(variants) == 1:
        return [variants[0][2]]
    label = versioned_changes[0][1].get("label")
    return [
        {**change, "label": f"{label} ({'/'.join(versions)})"}
        for _, _, change, versions in variants
    ]
