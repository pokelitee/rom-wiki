from __future__ import annotations

from typing import Any

from romwiki.pipeline.comparisons import (
    RECORD_KEY_FIELDS,
    comparison_by_key,
    records_by_key,
)
from romwiki.util.errors import DataSourceError


def merge_version_datasets(
    primary: dict[str, Any],
    primary_version: str,
    secondary: dict[str, Any],
    secondary_version: str,
) -> dict[str, Any]:
    """Combine two sibling-version datasets (e.g. Black and White) into one.

    Unlike `compare_datasets` (hack vs. clean-base, where "removed"/"changed"
    describe a mutation), sibling versions are co-equal: a record present in
    only one carries just that version's tag, and one present in both with
    identical content is tagged with both. Each record keeps its full,
    original fields (needed for rendering) plus a `versions` list; a record
    whose content actually differs between versions keeps the primary
    version's fields for rendering but also carries both raw variants under
    `version_variants`, since this codebase has no existing UI for showing
    two full alternate records side by side on one page.
    """
    kind = primary.get("dataset")
    if kind != secondary.get("dataset") or kind not in RECORD_KEY_FIELDS:
        raise DataSourceError("Version-merge datasets must have the same supported kind")
    key_name = RECORD_KEY_FIELDS[kind]
    primary_records = records_by_key(primary, key_name)
    secondary_records = records_by_key(secondary, key_name)

    merged_records = []
    for key in sorted(set(primary_records) | set(secondary_records), key=str):
        first = primary_records.get(key)
        second = secondary_records.get(key)
        if first is not None and second is not None:
            versions = [primary_version, secondary_version]
            record = dict(first)
            if first != second:
                record["version_variants"] = {
                    primary_version: first,
                    secondary_version: second,
                }
        elif first is not None:
            versions = [primary_version]
            record = dict(first)
        else:
            versions = [secondary_version]
            record = dict(second)
        record["versions"] = versions
        merged_records.append(record)

    return {
        **primary,
        "game": f"{primary_version}-{secondary_version}",
        "source": {
            primary_version: primary.get("source"),
            secondary_version: secondary.get("source"),
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
    """Combine two hack-vs-base comparisons for a sibling-version site.

    Matching comparison rows retain the ordinary single-game shape consumed
    by existing renderers. Rows whose values differ retain both complete
    comparisons under ``version_comparisons`` so detail pages can present
    each hack against its corresponding clean base without conflating them.
    """
    kind = primary.get("kind")
    if (
        kind != secondary.get("kind")
        or primary.get("dataset") != f"{kind}_comparison"
        or secondary.get("dataset") != f"{kind}_comparison"
        or kind not in RECORD_KEY_FIELDS
    ):
        raise DataSourceError(
            "Version-merge comparisons must have the same supported kind"
        )
    if primary.get("coverage") != secondary.get("coverage"):
        raise DataSourceError("Version-merge comparisons must have matching coverage")

    primary_records = comparison_by_key(primary)
    secondary_records = comparison_by_key(secondary)
    merged_records = []
    counts = {status: 0 for status in ("unchanged", "changed", "added", "removed")}
    for key in sorted(set(primary_records) | set(secondary_records), key=str):
        first = primary_records.get(key)
        second = secondary_records.get(key)
        if first is not None and second is not None:
            record = dict(first)
            record["versions"] = [primary_version, secondary_version]
            if first != second:
                variants = {
                    primary_version: {
                        **first,
                        "baseline": primary.get("baseline"),
                    },
                    secondary_version: {
                        **second,
                        "baseline": secondary.get("baseline"),
                    },
                }
                record["version_comparisons"] = variants
                statuses = {first["status"], second["status"]}
                record["status"] = (
                    statuses.pop() if len(statuses) == 1 else _combined_status(statuses)
                )
                record["changes"] = _combined_changes(first, second)
                record["detail_available"] = bool(
                    first.get("detail_available") or second.get("detail_available")
                )
        elif first is not None:
            record = {
                **first,
                "versions": [primary_version],
            }
        else:
            record = {
                **second,
                "versions": [secondary_version],
            }
        counts[record["status"]] += 1
        merged_records.append(record)

    return {
        **primary,
        "game": f"{primary_version}-{secondary_version}",
        "baseline": f"{primary.get('baseline')} / {secondary.get('baseline')}",
        "source": {
            primary_version: primary.get("source"),
            secondary_version: secondary.get("source"),
        },
        "counts": counts,
        "records": merged_records,
    }


def _combined_status(statuses: set[str]) -> str:
    for status in ("changed", "added", "removed", "unchanged"):
        if status in statuses:
            return status
    raise DataSourceError("Version comparison has no supported status")


def _combined_changes(
    primary: dict[str, Any], secondary: dict[str, Any]
) -> list[dict[str, Any]]:
    changes = []
    fields = set()
    for entry in (primary, secondary):
        for change in entry.get("changes", []):
            field = change.get("field", change.get("label"))
            if field not in fields:
                fields.add(field)
                changes.append(change)
    return changes
