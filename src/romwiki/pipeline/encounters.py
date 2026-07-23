from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION

from romwiki.engines.registry import get_engine
from romwiki.platforms.registry import get_platform
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.pipeline.identify import InspectionResult
from romwiki.schema.encounters import EncounterLocation


def extract_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for encounter extraction")
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
        "records": records,
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
    with result.image.path.open("rb") as stream:
        stream.seek(result.image.header.arm9_offset + table_offset)
        header_data = stream.read(count * engine.MAP_HEADER_SIZE)
    headers = engine.parse_platinum_map_headers(
        header_data,
        filesystem.read(layout["map_names"]),
        count=count,
    )
    messages = platform.archive_cls.from_bytes(filesystem.read(layout["messages"]))
    member = parameters["location_names_member"]
    location_names = engine.parse_english_message_archive(messages.read(member))

    locations: dict[int, list[EncounterLocation]] = {}
    null_encounter_id = profile.parameters.get(
        "null_encounter_id", engine.GEN4_ARCHIVE_MEMBER_NONE
    )
    for header in headers:
        if header.encounter_id == null_encounter_id:
            continue
        if header.encounter_id >= encounter_count:
            raise InvalidRomError(
                f"Map header {header.header_id} references missing encounter "
                f"member {header.encounter_id}"
            )
        if header.location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing location name "
                f"{header.location_name_id}"
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
