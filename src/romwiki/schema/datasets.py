from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from romwiki.util.errors import DataSourceError


class DatasetEnvelope(TypedDict):
    schema_version: int
    game: str
    engine: str
    dataset: str
    record_count: int
    source: dict[str, Any]


def dataset_envelope(
    *,
    schema_version: int,
    game: str,
    engine: str,
    dataset: str,
    source: dict[str, Any],
    records: list[Any],
) -> dict[str, Any]:
    """Construct the required normalized dataset fields in canonical order."""
    return {
        "schema_version": schema_version,
        "game": game,
        "engine": engine,
        "dataset": dataset,
        "record_count": len(records),
        "source": source,
        "records": records,
    }


def validate_dataset_envelope(
    dataset: Mapping[str, Any], *, context: str
) -> DatasetEnvelope:

    required_types = {
        "schema_version": int,
        "game": str,
        "engine": str,
        "dataset": str,
        "record_count": int,
        "source": dict,
    }
    invalid = [
        name
        for name, expected_type in required_types.items()
        if not isinstance(dataset.get(name), expected_type)
        or isinstance(dataset.get(name), bool)
    ]
    if invalid:
        fields = ", ".join(invalid)
        raise DataSourceError(f"Invalid {context} dataset envelope fields: {fields}")
    # Not every dataset kind carries a `records` list (a handful of pickup
    # datasets report a single logical record through kind-specific fields
    # like `tables`/`level_ranges` instead), so this only validates the
    # field when present -- but where it is present, it must actually be a
    # list whose length matches the envelope's own declared `record_count`,
    # catching a corrupted or stale payload rather than trusting the count.
    if "records" in dataset:
        records = dataset["records"]
        if not isinstance(records, list):
            raise DataSourceError(f"Invalid {context} dataset envelope fields: records")
        if len(records) != dataset["record_count"]:
            raise DataSourceError(
                f"{context} dataset record_count ({dataset['record_count']}) does not "
                f"match its records list ({len(records)})"
            )
    return dataset  # type: ignore[return-value]
