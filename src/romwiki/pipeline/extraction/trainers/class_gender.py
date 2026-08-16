from __future__ import annotations

from dataclasses import replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.engines.trainer_variants import resolve_trainer_variants
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.extraction.trainers.support import (
    read_rematch_table,
    read_starter_branch_families,
    read_starter_species,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import TrainerLocation, TrainerScriptReference
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import (
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINERS_RAW_SCHEMA_VERSION,
)
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_class_gender_trainer_dataset(
    result: InspectionResult,
) -> dict[str, Any]:
    profile = result.match.profile
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
    trainer_archive_options = {
        "allow_truncated": profile.parameters.get(
            "trainer_archives_allow_truncated", False
        )
    }
    trainers = platform.archive_cls.from_bytes(
        filesystem.read(trainer_path), **trainer_archive_options
    )
    parties = platform.archive_cls.from_bytes(
        filesystem.read(party_path), **trainer_archive_options
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    reference_names = extract_reference_names(profile, filesystem, messages)
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = engine.parse_english_message_archive(messages.read(names_member))
    classes = engine.parse_english_message_archive(messages.read(classes_member))
    arm9_data = read_code_binary(platform, result.image, engine)
    class_genders = engine.parse_trainer_class_genders(
        arm9_data[class_gender_offset : class_gender_offset + len(classes)],
        count=len(classes),
    )
    class_prize_overlay_id = profile.parameters.get("trainer_class_prize_overlay_id")
    class_prize_offset = profile.parameters.get("trainer_class_prize_offset")
    class_prize_multipliers = None
    if class_prize_overlay_id is not None and class_prize_offset is not None:
        _, prize_overlay = platform.read_overlay(result.image, class_prize_overlay_id)
        class_prize_multipliers = engine.parse_trainer_class_prize_multipliers(
            prize_overlay[class_prize_offset : class_prize_offset + len(classes)],
            count=len(classes),
        )
    if len(names) < len(trainers.members):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    first_trainer_id = getattr(engine, "FIRST_TRAINER_ID", 0)
    parsed_records = [
        engine.parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[member.index],
            class_names=classes,
            class_genders=class_genders,
            class_prize_multipliers=class_prize_multipliers,
            trainer_archive=trainer_path,
            party_archive=party_path,
        )
        for member in trainers.members[first_trainer_id:]
    ]
    (
        locations_by_trainer,
        script_references_by_trainer,
        location_source,
    ) = _extract_class_gender_trainer_locations(
        engine,
        platform,
        result,
        filesystem,
        messages,
        arm9_data,
        trainer_count=len(trainers.members),
    )
    records = [
        {
            **replace(
                record,
                locations=tuple(locations_by_trainer.get(record.trainer_id, ())),
                script_references=tuple(
                    script_references_by_trainer.get(record.trainer_id, ())
                ),
            ).to_dict(),
            **(
                {
                    "victory_money_multiplier_provenance": {
                        "source": "rom",
                        "overlay_id": class_prize_overlay_id,
                        "offset": class_prize_offset + record.class_id,
                        "class_id": record.class_id,
                    }
                }
                if class_prize_offset is not None
                else {}
            ),
        }
        for record in parsed_records
    ]
    rematch_source, rematch_chains = read_rematch_table(
        profile, platform, engine, result, trainer_count=len(trainers.members)
    )
    starter_species = read_starter_species(profile, platform, engine, result)
    starter_families = read_starter_branch_families(
        profile,
        platform,
        engine,
        filesystem,
        trainer_count=len(trainers.members),
        starter_species=starter_species,
    )
    selector_data = {
        key: value
        for key, value in (
            ("rematch_chains", rematch_chains),
            ("starter_branch_families", starter_families),
            # Branch conditions name the species the ROM itself compares, so the
            # resolver needs this profile's own species names.
            ("species_names", reference_names.get("pokemon_names")),
        )
        if value is not None
    }
    variant_contract = resolve_trainer_variants(
        engine, profile.id, profile.parameters, records, selector_data or None
    )
    envelope = dataset_envelope(
        schema_version=TRAINERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="trainers",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
            "trainer_class_genders": {
                "arm9_offset": class_gender_offset,
                "count": len(class_genders),
            },
            "trainer_class_prize_multipliers": (
                {
                    "overlay_id": class_prize_overlay_id,
                    "offset": class_prize_offset,
                    "count": len(class_prize_multipliers),
                }
                if class_prize_multipliers is not None
                else None
            ),
            "trainer_rematch_table": rematch_source,
            **location_source,
        },
        records=records,
    )
    envelope["battle_family_schema_version"] = TRAINER_BATTLE_FAMILY_SCHEMA_VERSION
    envelope.update(variant_contract)
    envelope["linked_record_count"] = sum(
        bool(record["locations"] or record["script_references"]) for record in records
    )
    envelope["location_reference_count"] = sum(
        len(record["locations"]) for record in records
    )
    envelope["script_reference_count"] = sum(
        len(record["script_references"]) for record in records
    )
    envelope.update(reference_names)
    return envelope


def _extract_class_gender_trainer_locations(
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
    if not getattr(engine, "TRAINER_LOCATION_EXTRACTION", True):
        return {}, {}, {"trainer_locations": "unsupported"}
    try:
        events_path = profile.layout["events"]
        scripts_path = profile.layout["scripts"]
        map_names_path = profile.layout["map_names"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer location metadata: {error.args[0]}"
        ) from error
    null_event_id = profile.parameters.get("null_event_id", engine.ARCHIVE_MEMBER_NONE)
    script_start = profile.parameters.get(
        "trainer_script_start", engine.TRAINER_OBJECT_SCRIPT_START
    )
    script_end = profile.parameters.get(
        "trainer_script_end", engine.TRAINER_OBJECT_SCRIPT_END
    )
    trainer_id_offset = profile.parameters.get(
        "trainer_script_id_offset", engine.TRAINER_OBJECT_ID_OFFSET
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
    event_options = {}
    if profile.parameters.get("events_allow_incorrect_data_block_size", False):
        event_options["allow_incorrect_data_block_size"] = True
    events = platform.archive_cls.from_bytes(
        filesystem.read(events_path), **event_options
    )
    extract_script_references = getattr(
        engine, "TRAINER_SCRIPT_REFERENCE_EXTRACTION", True
    )
    scripts = (
        platform.archive_cls.from_bytes(
            filesystem.read(scripts_path), allow_truncated=True
        )
        if extract_script_references
        else None
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
                    events.read(header.event_file_id),
                    event_file_id=header.event_file_id,
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
        if not extract_script_references:
            continue
        assert scripts is not None
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
    return (
        locations,
        script_references,
        {
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
            }
            if extract_script_references
            else "unsupported",
        },
    )
