from __future__ import annotations

from typing import Any, TypedDict

from romwiki.util.errors import DataSourceError


class DatasetEnvelope(TypedDict):
    schema_version: int
    game: str
    engine: str
    dataset: str
    record_count: int
    source: dict[str, Any]


def validate_dataset_envelope(
    dataset: dict[str, Any], *, context: str
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
    return dataset  # type: ignore[return-value]
