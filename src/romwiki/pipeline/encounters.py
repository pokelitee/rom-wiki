from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    MAP_HEADER_SIZE,
    parse_encounter_record,
    parse_english_message_archive,
    parse_platinum_map_headers,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem
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

    filesystem = NintendoDSFileSystem.from_image(result.image)
    archive = NarcArchive.from_bytes(filesystem.read(archive_path))
    parsed_records = [
        parse_encounter_record(
            archive.read(member.index),
            area_id=member.index,
            archive_path=archive_path,
        )
        for member in archive.members
    ]
    locations_by_encounter, location_source = _extract_encounter_locations(
        result, filesystem, encounter_count=len(parsed_records)
    )
    records = [
        replace(
            record,
            locations=tuple(locations_by_encounter.get(record.area_id, ())),
        ).to_dict()
        for record in parsed_records
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
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
    result: InspectionResult,
    filesystem: NintendoDSFileSystem,
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
        "null_encounter_id",
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
        header_data = stream.read(count * MAP_HEADER_SIZE)
    headers = parse_platinum_map_headers(
        header_data,
        filesystem.read(layout["map_names"]),
        count=count,
    )
    messages = NarcArchive.from_bytes(filesystem.read(layout["messages"]))
    member = parameters["location_names_member"]
    location_names = parse_english_message_archive(messages.read(member))

    locations: dict[int, list[EncounterLocation]] = {}
    null_encounter_id = parameters["null_encounter_id"]
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
