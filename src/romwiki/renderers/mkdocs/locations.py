from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.transforms.relationships import RelationshipIndex
from romwiki.renderers.mkdocs.location_encounter_map import (
    render_encounter_map_location_pages,
)
from romwiki.renderers.mkdocs.location_event_map import render_event_map_location_pages
from romwiki.renderers.mkdocs.references import ReferenceIndex
from romwiki.schema.rendering import LocationRenderRecord, RenderDataset


def render_location_pages(
    dataset: RenderDataset[LocationRenderRecord],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    encounter_comparison: dict[str, Any] | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    engine_id = dataset.get("engine")
    encounter_map = (
        get_engine(engine_id).formats.locations == "encounter-map"
        if isinstance(engine_id, str)
        else bool(dataset.get("records"))
        and "encounter_map_index" in dataset["records"][0]
    )
    if encounter_map:
        return render_encounter_map_location_pages(
            dataset,
            output_root,
            comparison,
            references,
            relationships,
            encounter_comparison,
            only_pages=only_pages,
        )
    return render_event_map_location_pages(
        dataset,
        output_root,
        comparison,
        references,
        relationships,
        encounter_comparison,
        only_pages=only_pages,
    )
