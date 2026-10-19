from __future__ import annotations

from dataclasses import replace
from typing import Any

from romwiki.engines.concerns import EncounterConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import iter_gba_map_headers
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.encounters import EncounterLocation, EncounterMethod
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


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
    see `parse_header`) to the location record for that map.

    Optional: a profile without `gmapgroups_offset` keeps every record's
    `locations=()`.
    """
    if "gmapgroups_offset" not in profile.parameters:
        return {}
    headers = {
        (header.map_group, header.map_num): header
        for header in iter_gba_map_headers(engine, platform, result.image, profile)
    }
    locations: dict[int, tuple[EncounterLocation, ...]] = {}
    for record in parsed_records:
        header = headers.get((record.map_group, record.map_num))
        if header is None:
            raise InvalidRomError(
                f"Gen III wild encounter map {record.map_group}.{record.map_num} "
                "is not a named map in gMapGroups"
            )
        locations[record.area_id] = (
            EncounterLocation(
                header_id=header.header_id,
                internal_name="",
                location_name_id=0,
                name=header.name,
            ),
        )
    return locations
