from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    iter_gba_map_headers,
    read_region_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_gba_map_groups_location_dataset(
    result: InspectionResult,
) -> dict[str, Any]:
    """One location per Generation III map, in `gMapGroups` order."""
    assert result.match is not None
    profile = result.match.profile
    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).locations
    headers = list(iter_gba_map_headers(engine, platform, result.image, profile))
    gmapgroups_offset = profile.int_parameter("gmapgroups_offset")
    region_name_offset = profile.int_parameter("region_name_offset")
    records = [
        record.to_dict()
        for record in engine.parse_map_header_table(
            b"".join(header.data for header in headers),
            read_region_names(engine, platform, result.image, profile),
            header_ids=[header.header_id for header in headers],
            archive_path=f"gMapGroups:{gmapgroups_offset:#x}",
        )
    ]
    return dataset_envelope(
        schema_version=LOCATIONS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="locations",
        source={
            "gmapgroups_offset": gmapgroups_offset,
            "region_name_offset": region_name_offset,
        },
        records=records,
    )
