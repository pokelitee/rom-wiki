from __future__ import annotations

from dataclasses import replace
from typing import Any

from romwiki.engines.concerns import EncounterConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    iter_segment_map_headers,
    read_region_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.encounters import EncounterLocation, EncounterMethod
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_method_table_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    # Generation III's wild-encounter mechanics (a flat per-map header table,
    # each of up to 4 methods reached through a pointer to a small
    # {rate, pointer-to-slots} struct -- a second level of pointer
    # indirection no other domain in this engine has needed) don't share
    # either Gen4's conditional shape or Gen5's seasonal shape, so this is a
    # standalone extraction path, the flat-offset analog of the archive
    # paths above.
    assert result.match is not None
    profile = result.match.profile
    try:
        offset = profile.parameters["encounter_offset"]
        count = profile.parameters["encounter_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define encounter_offset/encounter_count"
        ) from error
    if not isinstance(offset, int) or not isinstance(count, int):
        raise ProfileError(f"Profile {profile.id} has an invalid encounter parameter")

    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).encounters
    header_size = engine.ENCOUNTER_HEADER_SIZE
    header_data = platform.read_bytes(result.image, offset, header_size * count)
    archive_path = f"offset:{offset:#x}"

    parsed_records = []
    for map_index in range(count):
        header = header_data[map_index * header_size : (map_index + 1) * header_size]
        map_group, map_num, pointers = engine.parse_header(header, map_index=map_index)
        methods: dict[str, Any] = {}
        for name in engine.ENCOUNTER_METHOD_NAMES:
            pointer = pointers[name]
            if pointer == 0:
                continue
            info_offset = engine.resolve_gba_pointer(pointer)
            info_data = platform.read_bytes(result.image, info_offset, 8)
            rate, slots_pointer = engine.parse_method_info(
                info_data, map_index=map_index, name=name
            )
            slot_count = {
                "land": engine.ENCOUNTER_LAND_SLOT_COUNT,
                "water": engine.ENCOUNTER_WATER_SLOT_COUNT,
                "rock_smash": engine.ENCOUNTER_ROCK_SMASH_SLOT_COUNT,
                "fishing": engine.ENCOUNTER_FISHING_SLOT_COUNT,
            }[name]
            slots_offset = engine.resolve_gba_pointer(slots_pointer)
            slots_data = platform.read_bytes(result.image, slots_offset, slot_count * 4)
            slots = engine.parse_method_slots(
                slots_data, map_index=map_index, name=name, count=slot_count
            )
            methods[name] = EncounterMethod(rate=rate, slots=slots)
        record = engine.parse_encounter_record(
            map_group,
            map_num,
            methods,
            map_index=map_index,
            archive_path=archive_path,
        )
        parsed_records.append(record)

    # Only maps within the already-verified Sevii Islands/postgame
    # `map_header_segments` span can be linked -- Kanto's own maps have no
    # corresponding location record yet (see `locations.py`'s module
    # comment), so those records keep `locations=()`.
    locations_by_map_index = _extract_gen3_encounter_locations(
        platform, result, profile, engine, parsed_records
    )
    records = [
        replace(
            record, locations=locations_by_map_index.get(record.area_id, ())
        ).to_dict()
        for record in parsed_records
    ]

    envelope = dataset_envelope(
        schema_version=ENCOUNTERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="wild_encounters",
        source={"rom_sha256": result.image.hashes.sha256, "offset": offset},
        records=records,
    )
    return envelope


def _extract_gen3_encounter_locations(
    platform: Any,
    result: InspectionResult,
    profile: Any,
    engine: EncounterConcern,
    parsed_records: list[Any],
) -> dict[int, tuple[EncounterLocation, ...]]:
    """Link each Generation III wild-encounter map (`map_group`/`map_num`,
    see `parse_header`) to the location record it corresponds to, when that
    map falls within the already-verified `map_header_segments` span.

    Independently re-decodes both `map_header_segments` (the same way
    `flat_header_segments.py` does for the `locations` domain) and
    `gMapGroups` (the two-level pointer structure those segments are
    actually reached through in-game, see `constants.py`'s
    `GMAPGROUPS_GROUP_COUNT` comment) rather than depending on the
    `locations` domain's own extraction output -- the same "each domain
    independently re-decodes the shared table" pattern already used by the
    NDS engines' `battle_mode.py`/`encounters.py` location backfills.

    Optional: a profile whose engine doesn't implement the `locations`
    domain yet (e.g. Emerald) simply gets every record's `locations=()`,
    the same "optional enrichment input" precedent as
    `_extract_seasonal_wild_map_names` above.
    """
    location_params = (
        "map_header_segments",
        "region_name_offset",
        "region_name_count",
        "gmapgroups_offset",
    )
    if not all(name in profile.parameters for name in location_params):
        return {}
    segments = profile.parameters["map_header_segments"]
    region_name_offset = profile.int_parameter("region_name_offset")
    region_name_count = profile.int_parameter("region_name_count")
    gmapgroups_offset = profile.int_parameter("gmapgroups_offset")

    region_names = read_region_names(
        engine,
        platform,
        result.image,
        offset=region_name_offset,
        count=region_name_count,
    )
    header_by_address = {
        engine.gba_pointer_for_offset(header.rom_offset): (
            header.header_id,
            header.name,
        )
        for header in iter_segment_map_headers(
            engine, platform, result.image, segments, region_names
        )
    }

    group_pointer_data = platform.read_bytes(
        result.image, gmapgroups_offset, engine.GMAPGROUPS_GROUP_COUNT * 4
    )
    group_pointers = engine.parse_gmapgroups_pointers(
        group_pointer_data, group_count=engine.GMAPGROUPS_GROUP_COUNT
    )
    gmapgroups_address = engine.gba_pointer_for_offset(gmapgroups_offset)
    subtable_start = engine.resolve_gba_pointer(group_pointers[0])
    subtable_data = platform.read_bytes(
        result.image, subtable_start, gmapgroups_address - group_pointers[0]
    )
    group_num_to_address = engine.parse_map_group_index(
        group_pointers, subtable_data, gmapgroups_address=gmapgroups_address
    )

    locations: dict[int, tuple[EncounterLocation, ...]] = {}
    for record in parsed_records:
        address = group_num_to_address.get((record.map_group, record.map_num))
        if address is None:
            continue
        header = header_by_address.get(address)
        if header is None:
            continue
        header_id, name = header
        locations[record.area_id] = (
            EncounterLocation(
                header_id=header_id,
                internal_name="",
                location_name_id=0,
                name=name,
            ),
        )
    return locations
