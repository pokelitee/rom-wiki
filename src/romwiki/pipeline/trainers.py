from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.map_headers import read_code_binary, resolve_map_headers
from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.platforms.registry import get_platform
from romwiki.schema import TrainerLocation, TrainerScriptReference
from romwiki.schema.versions import TRAINERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    if profile.engine == "gen5_bw":
        return _extract_gen5_trainer_dataset(result)
    try:
        trainer_path = profile.layout["trainer_data"]
        party_path = profile.layout["trainer_parties"]
        messages_path = profile.layout["messages"]
        names_member = profile.parameters["trainer_names_member"]
        classes_member = profile.parameters["trainer_classes_member"]
        class_gender_offset = profile.parameters["trainer_class_gender_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).trainers
    filesystem = platform.filesystem_from_image(result.image)
    trainers = platform.archive_cls.from_bytes(filesystem.read(trainer_path))
    parties = platform.archive_cls.from_bytes(filesystem.read(party_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    reference_names = extract_reference_names(profile, filesystem, messages)
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = engine.parse_english_message_archive(messages.read(names_member))
    classes = engine.parse_english_message_archive(messages.read(classes_member))
    arm9_data = read_code_binary(platform, result.image)
    class_genders = engine.parse_trainer_class_genders(
        arm9_data[class_gender_offset : class_gender_offset + len(classes)],
        count=len(classes),
    )
    if len(names) < len(trainers.members):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    parsed_records = [
        engine.parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[member.index],
            class_names=classes,
            class_genders=class_genders,
            trainer_archive=trainer_path,
            party_archive=party_path,
        )
        for member in trainers.members
    ]
    (
        locations_by_trainer,
        script_references_by_trainer,
        location_source,
    ) = _extract_trainer_locations(
        engine,
        platform,
        result,
        filesystem,
        messages,
        arm9_data,
        trainer_count=len(parsed_records),
    )
    records = [
        replace(
            record,
            locations=tuple(locations_by_trainer.get(record.trainer_id, ())),
            script_references=tuple(
                script_references_by_trainer.get(record.trainer_id, ())
            ),
        ).to_dict()
        for record in parsed_records
    ]
    return {
        "schema_version": TRAINERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "trainers",
        "record_count": len(records),
        "linked_record_count": sum(
            bool(record["locations"] or record["script_references"])
            for record in records
        ),
        "location_reference_count": sum(len(record["locations"]) for record in records),
        "script_reference_count": sum(
            len(record["script_references"]) for record in records
        ),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
            "trainer_class_genders": {
                "arm9_offset": class_gender_offset,
                "count": len(class_genders),
            },
            **location_source,
        },
        **reference_names,
        "records": records,
    }


def _extract_gen5_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    # This generation's trainer/party record shape is close enough to Gen
    # IV's to reuse the same schema-level idea (header + party array with
    # optional held-item/custom-move blocks), but real map locations/script
    # references aren't attached yet -- see gen5_bw/__init__.py's module
    # docstring for why -- so every trainer's `locations`/`script_references`
    # stay empty. Member 0 of both archives is an unused, differently-shaped
    # placeholder (confirmed against real ROM data: 16 bytes vs. the normal
    # 20, 6 bytes vs. a real party record), so real trainer IDs start at 1;
    # trainer names are indexed by trainer_id - 1 (Gen5RomHandler.java's own
    # `tnames.get(i - 1)`).
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

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).trainers
    filesystem = platform.filesystem_from_image(result.image)
    trainers = platform.archive_cls.from_bytes(filesystem.read(trainer_path))
    parties = platform.archive_cls.from_bytes(filesystem.read(party_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    reference_names = extract_reference_names(profile, filesystem, messages)
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = engine.parse_english_message_archive(messages.read(names_member))
    classes = engine.parse_english_message_archive(messages.read(classes_member))
    if len(names) < len(trainers.members) - 1:
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    records = [
        engine.parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[member.index - 1],
            class_names=classes,
            trainer_archive=trainer_path,
            party_archive=party_path,
        ).to_dict()
        for member in trainers.members
        if member.index != 0
    ]
    return {
        "schema_version": TRAINERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "trainers",
        "record_count": len(records),
        "linked_record_count": 0,
        "location_reference_count": 0,
        "script_reference_count": 0,
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
        },
        **reference_names,
        "records": records,
    }


def _extract_trainer_locations(
    engine: Any,
    platform: Any,
    result: InspectionResult,
    filesystem: Any,
    messages: Any,
    arm9_data: bytes,
    *,
    trainer_count: int,
) -> tuple[
    dict[int, list[TrainerLocation]],
    dict[int, list[TrainerScriptReference]],
    dict[str, Any],
]:
    assert result.match is not None
    profile = result.match.profile
    try:
        events_path = profile.layout["events"]
        scripts_path = profile.layout["scripts"]
        map_names_path = profile.layout["map_names"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        script_start = profile.parameters["trainer_script_start"]
        script_end = profile.parameters["trainer_script_end"]
        trainer_id_offset = profile.parameters["trainer_script_id_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer location metadata: {error.args[0]}"
        ) from error
    null_event_id = profile.parameters.get(
        "null_event_id", engine.ARCHIVE_MEMBER_NONE
    )

    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=map_names_path,
        table_offset=table_offset,
        count=count,
        location_names_member=location_names_member,
    )
    events = platform.archive_cls.from_bytes(filesystem.read(events_path))
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), allow_truncated=True
    )
    object_cache: dict[int, tuple[Any, ...]] = {}
    script_cache: dict[int, tuple[Any, ...]] = {}
    locations: dict[int, list[TrainerLocation]] = {}
    script_references: dict[int, list[TrainerScriptReference]] = {}

    for header in headers:
        objects: tuple[Any, ...] = ()
        if header.event_file_id != null_event_id:
            if header.event_file_id >= len(events.members):
                raise InvalidRomError(
                    f"Map header {header.header_id} references missing event file "
                    f"{header.event_file_id}"
                )
            if header.event_file_id not in object_cache:
                object_cache[header.event_file_id] = engine.parse_object_events(
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
        if header.script_file_id >= len(scripts.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing script file "
                f"{header.script_file_id}"
            )
        if header.script_file_id not in script_cache:
            script_cache[header.script_file_id] = engine.parse_trainer_battle_commands(
                scripts.read(header.script_file_id), trainer_count=trainer_count
            )
        for command in script_cache[header.script_file_id]:
            for opponent_slot, trainer_id in enumerate(command.trainer_ids, start=1):
                script_references.setdefault(trainer_id, []).append(
                    TrainerScriptReference(
                        header_id=header.header_id,
                        internal_name=header.internal_name,
                        location_name_id=header.location_name_id,
                        name=location_names[header.location_name_id],
                        script_file_id=header.script_file_id,
                        command_offset=command.offset,
                        opponent_slot=opponent_slot,
                    )
                )
    return locations, script_references, {
        "trainer_locations": {
            "events_archive": events_path,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "location_names_member": location_names_member,
            "script_range": [script_start, script_end],
            "trainer_id_offset": trainer_id_offset,
        },
        "trainer_script_references": {
            "scripts_archive": scripts_path,
            "start_trainer_battle_opcode": engine.START_TRAINER_BATTLE,
            "check_won_battle_opcode": engine.CHECK_WON_BATTLE,
            "literal_ids_only": True,
        },
    }


def write_trainer_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
