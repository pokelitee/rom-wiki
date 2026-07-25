from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.map_headers import read_code_binary, resolve_map_headers
from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.platforms.registry import get_platform
from romwiki.schema.encounters import EncounterLocation
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for encounter extraction")
    profile = result.match.profile
    if profile.engine == "gen5_bw":
        return _extract_gen5_encounter_dataset(result)
    try:
        archive_path = profile.layout["encounters"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define an encounter archive"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).encounters
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    parsed_records = [
        engine.parse_encounter_record(
            archive.read(member.index),
            area_id=member.index,
            archive_path=archive_path,
        )
        for member in archive.members
    ]
    locations_by_encounter, location_source = _extract_encounter_locations(
        engine, platform, result, filesystem, encounter_count=len(parsed_records)
    )
    records = [
        replace(
            record,
            locations=tuple(locations_by_encounter.get(record.area_id, ())),
        ).to_dict()
        for record in parsed_records
    ]
    return {
        "schema_version": ENCOUNTERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "wild_encounters",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
            **location_source,
        },
        **reference_names,
        "records": records,
    }


def _extract_gen5_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    # This generation's wild-encounter mechanics (seven encounter methods per
    # area, up to four seasonal variants per map) don't share Gen4's shape
    # (walking/surf/rod/swarm/day/night/radar/dual-slot/Unown), so this is a
    # standalone extraction path rather than a variant of the one above.
    profile = result.match.profile
    try:
        archive_path = profile.layout["encounters"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define an encounter archive"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).encounters
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    areas = [
        area
        for member in archive.members
        for area in engine.parse_encounter_entry(
            archive.read(member.index),
            map_index=member.index,
            archive_path=archive_path,
        )
    ]
    wild_map_names, location_source = _extract_gen5_wild_map_names(
        result, engine, platform, filesystem
    )
    records = [
        replace(
            area,
            area_id=index,
            location_names=tuple(wild_map_names.get(area.map_index, ())),
        ).to_dict()
        for index, area in enumerate(areas)
    ]
    return {
        "schema_version": ENCOUNTERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "wild_encounters",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
            **location_source,
        },
        **reference_names,
        "records": records,
    }


def _extract_gen5_wild_map_names(
    result: InspectionResult, engine: Any, platform: Any, filesystem: Any
) -> tuple[dict[int, list[str]], dict[str, Any]]:
    # Optional: a profile that doesn't declare this yet (or a future
    # generation reusing this path) simply gets unnamed encounter areas,
    # same as every other optional enrichment input in this codebase.
    profile = result.match.profile
    if "map_headers" not in profile.layout or "map_names_member" not in profile.parameters:
        return {}, {}
    map_headers_path = profile.layout["map_headers"]
    map_names_member = profile.parameters["map_names_member"]
    messages_path = profile.layout["messages"]
    map_headers = platform.archive_cls.from_bytes(filesystem.read(map_headers_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    wild_map_names = engine.parse_wild_map_names(
        map_headers.read(0), map_names=tuple(map_names)
    )
    return wild_map_names, {
        "wild_map_names": {
            "map_headers_archive": map_headers_path,
            "map_names": {"archive": messages_path, "member": map_names_member},
        }
    }


def _extract_encounter_locations(
    engine: Any,
    platform: Any,
    result: InspectionResult,
    filesystem: Any,
    *,
    encounter_count: int,
) -> tuple[dict[int, list[EncounterLocation]], dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    required_layout = ("map_names", "messages")
    required_parameters = (
        "map_header_offset",
        "map_header_count",
        "location_names_member",
    )
    try:
        layout = {name: profile.layout[name] for name in required_layout}
        parameters = {
            name: profile.parameters[name] for name in required_parameters
        }
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing encounter location metadata: "
            f"{error.args[0]}"
        ) from error

    count = parameters["map_header_count"]
    table_offset = parameters["map_header_offset"]
    member = parameters["location_names_member"]
    arm9_data = read_code_binary(platform, result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(layout["messages"]))
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=layout["map_names"],
        table_offset=table_offset,
        count=count,
        location_names_member=member,
    )

    locations: dict[int, list[EncounterLocation]] = {}
    null_encounter_id = profile.parameters.get(
        "null_encounter_id", engine.ARCHIVE_MEMBER_NONE
    )
    for header in headers:
        if header.encounter_id == null_encounter_id:
            continue
        if header.encounter_id >= encounter_count:
            raise InvalidRomError(
                f"Map header {header.header_id} references missing encounter "
                f"member {header.encounter_id}"
            )
        locations.setdefault(header.encounter_id, []).append(
            EncounterLocation(
                header_id=header.header_id,
                internal_name=header.internal_name,
                location_name_id=header.location_name_id,
                name=location_names[header.location_name_id],
            )
        )
    return locations, {
        "map_headers": {
            "arm9_offset": table_offset,
            "count": count,
            "internal_names": layout["map_names"],
        },
        "location_names": {
            "archive": layout["messages"],
            "member": member,
        },
    }


def write_encounter_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
