from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.encounters.conditional import (
    extract_conditional_encounter_dataset,
)
from romwiki.pipeline.extraction.encounters.method_table import (
    extract_method_table_encounter_dataset,
)
from romwiki.pipeline.extraction.encounters.seasonal import (
    extract_seasonal_encounter_dataset,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.util.errors import DataSourceError, ProfileError


def extract_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for encounter extraction")
    encounter_format = get_engine(result.match.profile.engine).formats.encounters
    if encounter_format == "seasonal":
        return extract_seasonal_encounter_dataset(result)
    if encounter_format == "method-table":
        return extract_method_table_encounter_dataset(result)
    if encounter_format != "conditional":
        raise DataSourceError(f"Unsupported encounter format: {encounter_format!r}")
    return extract_conditional_encounter_dataset(result)
