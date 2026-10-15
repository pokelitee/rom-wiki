from __future__ import annotations

from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.schema.rendering import LocationDataset
from romwiki.schema.versions import LOCATIONS_ENRICHED_SCHEMA_VERSION


def enrich_location_dataset(dataset: dict[str, Any]) -> LocationDataset:
    """Publish normalized locations with the semantic shape renderers select."""
    return cast(
        LocationDataset,
        {
            **dataset,
            "schema_version": LOCATIONS_ENRICHED_SCHEMA_VERSION,
            "location_format": get_engine(dataset["engine"]).formats.locations,
        },
    )
