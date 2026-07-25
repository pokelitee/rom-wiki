from __future__ import annotations

from typing import Any

from romwiki.pipeline.comparisons import RECORD_KEY_FIELDS, records_by_key
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
