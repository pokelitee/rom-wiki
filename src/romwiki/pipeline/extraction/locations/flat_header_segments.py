from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_flat_header_segments_location_dataset(
    result: InspectionResult,
) -> dict[str, Any]:
    # Generation III (FireRed/LeafGreen)'s map headers live in `gMapGroups`,
    # a small array of pointers to each group's own separate, contiguous
    # array of full `MapHeader` structs -- not one flat table. A real-ROM
    # scan (see `gen3/shared/locations.py`'s module comment) found each
    # group's array as its own contiguous run, so `map_header_segments`
    # lists every verified `(offset, count)` run rather than a single
    # offset/count pair, the flat-offset analog of how
    # `encounters.py`'s `_extract_method_table_encounter_dataset` reads one
    # flat table -- here there are several, concatenated in profile order
    # to assign sequential synthetic `header_id`s.
    assert result.match is not None
    profile = result.match.profile
    try:
        segments = profile.parameters["map_header_segments"]
        region_name_offset = profile.parameters["region_name_offset"]
        region_name_count = profile.parameters["region_name_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define map_header_segments/"
            "region_name_offset/region_name_count"
        ) from error
    if not isinstance(segments, list) or not all(
        isinstance(segment, list)
        and len(segment) == 2
        and all(isinstance(value, int) for value in segment)
        for segment in segments
    ):
        raise ProfileError(
            f"Profile {profile.id} has an invalid map_header_segments parameter"
        )
    if not isinstance(region_name_offset, int) or not isinstance(
        region_name_count, int
    ):
        raise ProfileError(f"Profile {profile.id} has an invalid region_name parameter")

    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).locations

    header_data = b"".join(
        platform.read_bytes(result.image, offset, count * engine.MAP_HEADER_SIZE)
        for offset, count in segments
    )
    total_count = sum(count for _offset, count in segments)
    archive_path = "+".join(f"{offset:#x}" for offset, _count in segments)

    # `decode_gen3_text_sequence` scans for terminators starting at `offset`
    # within the given buffer, so the region-name table is read as one
    # oversized chunk (worst case, every entry uses its full padding budget)
    # rather than needing an exact byte length up front.
    region_name_data = platform.read_bytes(
        result.image, region_name_offset, region_name_count * 32
    )
    region_names = engine.decode_gen3_text_sequence(
        region_name_data, offset=0, count=region_name_count
    )

    records = [
        record.to_dict()
        for record in engine.parse_map_header_table(
            header_data,
            region_names,
            count=total_count,
            archive_path=archive_path,
        )
    ]
    return dataset_envelope(
        schema_version=LOCATIONS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="locations",
        source={"segments": archive_path, "region_name_offset": region_name_offset},
        records=records,
    )
