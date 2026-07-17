from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    MAP_HEADER_SIZE,
    parse_english_message_archive,
    parse_object_events,
    parse_platinum_map_headers,
    parse_trainer_record,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem
from romwiki.schema import TrainerLocation


def extract_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    try:
        trainer_path = profile.layout["trainer_data"]
        party_path = profile.layout["trainer_parties"]
        messages_path = profile.layout["messages"]
        names_member = profile.parameters["trainer_names_member"]
        classes_member = profile.parameters["trainer_classes_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer metadata: {error.args[0]}"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    trainers = NarcArchive.from_bytes(filesystem.read(trainer_path))
    parties = NarcArchive.from_bytes(filesystem.read(party_path))
    messages = NarcArchive.from_bytes(filesystem.read(messages_path))
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = parse_english_message_archive(messages.read(names_member))
    classes = parse_english_message_archive(messages.read(classes_member))
    if len(names) < len(trainers.members):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    parsed_records = [
        parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[member.index],
            class_names=classes,
            trainer_archive=trainer_path,
            party_archive=party_path,
        )
        for member in trainers.members
    ]
    locations_by_trainer, location_source = _extract_trainer_locations(
        result,
        filesystem,
        messages,
        trainer_count=len(parsed_records),
    )
    records = [
        replace(
            record,
            locations=tuple(locations_by_trainer.get(record.trainer_id, ())),
        ).to_dict()
        for record in parsed_records
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "trainers",
        "record_count": len(records),
        "linked_record_count": sum(bool(record["locations"]) for record in records),
        "location_reference_count": sum(len(record["locations"]) for record in records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
            **location_source,
        },
        "records": records,
    }


def _extract_trainer_locations(
    result: InspectionResult,
    filesystem: NintendoDSFileSystem,
    messages: NarcArchive,
    *,
    trainer_count: int,
) -> tuple[dict[int, list[TrainerLocation]], dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    try:
        events_path = profile.layout["events"]
        map_names_path = profile.layout["map_names"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        null_event_id = profile.parameters["null_event_id"]
        script_start = profile.parameters["trainer_script_start"]
        script_end = profile.parameters["trainer_script_end"]
        trainer_id_offset = profile.parameters["trainer_script_id_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer location metadata: {error.args[0]}"
        ) from error

    with result.image.path.open("rb") as stream:
        stream.seek(result.image.header.arm9_offset + table_offset)
        header_data = stream.read(count * MAP_HEADER_SIZE)
    headers = parse_platinum_map_headers(
        header_data, filesystem.read(map_names_path), count=count
    )
    location_names = parse_english_message_archive(messages.read(location_names_member))
    events = NarcArchive.from_bytes(filesystem.read(events_path))
    object_cache: dict[int, tuple[Any, ...]] = {}
    locations: dict[int, list[TrainerLocation]] = {}

    for header in headers:
        if header.event_file_id == null_event_id:
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing location name "
                f"{header.location_name_id}"
            )
        if header.event_file_id not in object_cache:
            object_cache[header.event_file_id] = parse_object_events(
                events.read(header.event_file_id), event_file_id=header.event_file_id
            )
        objects = object_cache[header.event_file_id]
        for object_event in objects:
            if object_event.trainer_type == 0:
                continue
            if not script_start <= object_event.script_id <= script_end:
                continue
            trainer_id = object_event.script_id - script_start + trainer_id_offset
            if not 0 <= trainer_id < trainer_count:
                raise InvalidRomError(
                    f"Trainer object in map header {header.header_id} resolves to "
                    f"missing trainer {trainer_id}"
                )
            locations.setdefault(trainer_id, []).append(
                TrainerLocation(
                    header_id=header.header_id,
                    internal_name=header.internal_name,
                    location_name_id=header.location_name_id,
                    name=location_names[header.location_name_id],
                    event_file_id=header.event_file_id,
                    object_index=object_event.index,
                    object_local_id=object_event.local_id,
                    script_id=object_event.script_id,
                    trainer_type=object_event.trainer_type,
                    x=object_event.x,
                    y=object_event.y,
                    z=object_event.z,
                )
            )
    return locations, {
        "trainer_locations": {
            "events_archive": events_path,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "location_names_member": location_names_member,
            "script_range": [script_start, script_end],
            "trainer_id_offset": trainer_id_offset,
        }
    }


def write_trainer_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output_path)
