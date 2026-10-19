from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.archive_encounter_map import (
    extract_archive_encounter_map_location_dataset,
)
from romwiki.pipeline.extraction.locations.arm9_encounter_map import (
    extract_arm9_encounter_map_location_dataset,
)
from romwiki.pipeline.extraction.locations.arm9_event_map import (
    extract_arm9_event_map_location_dataset,
)
from romwiki.pipeline.extraction.locations.gba_map_groups import (
    extract_gba_map_groups_location_dataset,
)
from romwiki.util.errors import DataSourceError, ProfileError


def extract_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
    mart_dataset: dict[str, Any] | None = None,
    trade_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for location extraction")
    profile = result.match.profile
    extraction_format = get_engine(profile.engine).formats.location_extraction
    if extraction_format == "archive-encounter-map":
        return extract_archive_encounter_map_location_dataset(
            result,
            trainer_dataset,
            static_encounter_dataset,
            item_dataset,
            mart_dataset,
            trade_dataset,
        )
    if extraction_format == "arm9-encounter-map":
        return extract_arm9_encounter_map_location_dataset(
            result, trainer_dataset=trainer_dataset, item_dataset=item_dataset
        )
    if extraction_format == "arm9-event-map":
        return extract_arm9_event_map_location_dataset(
            result,
            trainer_dataset,
            static_encounter_dataset,
            item_dataset,
            mart_dataset,
            trade_dataset,
        )
    if extraction_format == "gba-map-groups":
        return extract_gba_map_groups_location_dataset(result)
    raise DataSourceError(
        f"Unsupported location extraction format: {extraction_format!r}"
    )
