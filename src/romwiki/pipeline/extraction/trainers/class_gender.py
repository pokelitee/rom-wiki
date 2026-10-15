from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any, cast

from romwiki.engines.concerns import TrainerConcern
from romwiki.engines.registry import (
    COMPRESSED_CODE_BINARY,
    TAG_BATTLES,
    TRAINER_LOCATIONS,
    TRAINER_SCRIPT_REFERENCES,
    get_engine,
)
from romwiki.engines.trainer_variants import (
    TrainerVariantResolver,
    resolve_trainer_variants,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.extraction.trainers.support import (
    read_rematch_table,
    read_staged_partner_battle_families,
    read_starter_branch_families,
    read_starter_species,
    scripts_archive_options,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import TrainerLocation, TrainerScriptReference
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import (
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINERS_RAW_SCHEMA_VERSION,
)
from romwiki.util.errors import InvalidRomError, ProfileError


@dataclass(frozen=True)
class _ClassGenderLayout:
    trainer_path: str
    party_path: str
    messages_path: str
    names_member: int
    classes_member: int
    class_gender_offset: int


@dataclass(frozen=True)
class _ClassPrizeTable:
    overlay_id: int | None
    offset: int | None
    multipliers: Any


@dataclass(frozen=True)
class _TrainerLocationLayout:
    events_path: str
    scripts_path: str
    map_names_path: str
    count: int
    table_offset: int
    location_names_member: int
    null_event_id: int
    script_start: int
    script_end: int
    trainer_id_offset: int


@dataclass(frozen=True)
class _ClassGenderTrainers:
    messages: Any
    arm9_data: bytes
    reference_names: dict[str, Any]
    parsed_records: list[Any]
    trainer_count: int
    class_gender_count: int
    prize_table: _ClassPrizeTable


def extract_class_gender_trainer_dataset(
    result: InspectionResult,
) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    layout = _read_class_gender_layout(profile)

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).trainers
    filesystem = platform.filesystem_from_image(result.image)
    trainers = _decode_class_gender_trainers(
        profile, engine, platform, filesystem, result, layout
    )
    (
        locations_by_trainer,
        script_references_by_trainer,
        location_source,
        unresolved_trainer_location_count,
    ) = _extract_class_gender_trainer_locations(
        engine,
        platform,
        result,
        filesystem,
        trainers.messages,
        trainers.arm9_data,
        trainer_count=trainers.trainer_count,
    )
    records = [
        _link_class_gender_record(
            record,
            locations_by_trainer,
            script_references_by_trainer,
            trainers.prize_table,
        )
        for record in trainers.parsed_records
    ]
    rematch_source, variant_contract = _resolve_class_gender_variants(
        profile,
        platform,
        engine,
        result,
        filesystem,
        records,
        trainer_count=trainers.trainer_count,
        species_names=trainers.reference_names.get("pokemon_names"),
    )
    envelope = dataset_envelope(
        schema_version=TRAINERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="trainers",
        source={
            "rom_sha256": result.image.hashes.sha256,
            **_class_gender_source(
                layout, trainers.prize_table, trainers.class_gender_count
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
    envelope["unresolved_trainer_location_count"] = unresolved_trainer_location_count
    envelope["script_reference_count"] = sum(
        len(record["script_references"]) for record in records
    )
    envelope.update(trainers.reference_names)
    return envelope


def _decode_class_gender_trainers(
    profile: Any,
    engine: TrainerConcern,
    platform: Any,
    filesystem: Any,
    result: InspectionResult,
    layout: _ClassGenderLayout,
) -> _ClassGenderTrainers:
    trainer_archive_options = {
        "allow_truncated": profile.parameters.get(
            "trainer_archives_allow_truncated", False
        )
    }
    trainers = platform.archive_cls.from_bytes(
        filesystem.read(layout.trainer_path), **trainer_archive_options
    )
    parties = platform.archive_cls.from_bytes(
        filesystem.read(layout.party_path), **trainer_archive_options
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(layout.messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    reference_names = extract_reference_names(profile, filesystem, messages)
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = engine.parse_english_message_archive(messages.read(layout.names_member))
    classes = engine.parse_english_message_archive(messages.read(layout.classes_member))
    arm9_data = read_code_binary(
        platform,
        result.image,
        compressed=COMPRESSED_CODE_BINARY in get_engine(profile.engine).capabilities,
    )
    class_genders = engine.parse_trainer_class_genders(
        arm9_data[
            layout.class_gender_offset : layout.class_gender_offset + len(classes)
        ],
        count=len(classes),
    )
    prize_table = _read_class_prize_table(
        profile, platform, engine, result, class_count=len(classes)
    )
    if len(names) < len(trainers.members):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")
    return _ClassGenderTrainers(
        messages=messages,
        arm9_data=arm9_data,
        reference_names=reference_names,
        parsed_records=[
            engine.parse_trainer_record(
                trainers.read(member.index),
                parties.read(member.index),
                trainer_id=member.index,
                name=names[member.index],
                class_names=classes,
                class_genders=class_genders,
                class_prize_multipliers=prize_table.multipliers,
                trainer_archive=layout.trainer_path,
                party_archive=layout.party_path,
            )
            for member in trainers.members[engine.FIRST_TRAINER_ID :]
        ],
        trainer_count=len(trainers.members),
        class_gender_count=len(class_genders),
        prize_table=prize_table,
    )


def _read_class_gender_layout(profile: Any) -> _ClassGenderLayout:
    try:
        return _ClassGenderLayout(
            trainer_path=profile.layout["trainer_data"],
            party_path=profile.layout["trainer_parties"],
            messages_path=profile.layout["messages"],
            names_member=profile.parameters["trainer_names_member"],
            classes_member=profile.parameters["trainer_classes_member"],
            class_gender_offset=profile.parameters["trainer_class_gender_offset"],
        )
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer metadata: {error.args[0]}"
        ) from error


def _read_class_prize_table(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    result: InspectionResult,
    *,
    class_count: int,
) -> _ClassPrizeTable:
    overlay_id = profile.parameters.get("trainer_class_prize_overlay_id")
    offset = profile.parameters.get("trainer_class_prize_offset")
    multipliers = None
    if overlay_id is not None and offset is not None:
        if platform.read_overlay is None:
            raise ProfileError(
                f"Platform {profile.platform!r} does not support overlays"
            )
        _, prize_overlay = platform.read_overlay(result.image, overlay_id)
        multipliers = engine.parse_trainer_class_prize_multipliers(
            prize_overlay[offset : offset + class_count],
            count=class_count,
        )
    return _ClassPrizeTable(
        overlay_id=overlay_id, offset=offset, multipliers=multipliers
    )


def _link_class_gender_record(
    record: Any,
    locations_by_trainer: dict[int, list[TrainerLocation]],
    script_references_by_trainer: dict[int, list[TrainerScriptReference]],
    prize_table: _ClassPrizeTable,
) -> dict[str, Any]:
    return {
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
                    "overlay_id": prize_table.overlay_id,
                    "offset": prize_table.offset + record.class_id,
                    "class_id": record.class_id,
                }
            }
            if prize_table.offset is not None
            else {}
        ),
    }


def _resolve_class_gender_variants(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    result: InspectionResult,
    filesystem: Any,
    records: list[dict[str, Any]],
    *,
    trainer_count: int,
    species_names: Any,
) -> tuple[Any, dict[str, Any]]:
    rematch_source, rematch_chains = read_rematch_table(
        profile, platform, engine, result, trainer_count=trainer_count
    )
    starter_species = read_starter_species(profile, platform, engine, result)
    starter_families = read_starter_branch_families(
        profile,
        platform,
        engine,
        filesystem,
        trainer_count=trainer_count,
        starter_species=starter_species,
    )
    # Platinum's staged tag-battle partners follow the exact same
    # starter-branch shape (see `dppt/tag_battles.py`), so they merge into
    # the same selector list rather than needing their own resolver.
    staged_partner_families = read_staged_partner_battle_families(
        profile,
        platform,
        engine,
        filesystem,
        trainer_count=trainer_count,
        starter_species=starter_species,
    )
    if staged_partner_families:
        starter_families = (*(starter_families or ()), *staged_partner_families)
    selector_data = {
        key: value
        for key, value in (
            ("rematch_chains", rematch_chains),
            ("starter_branch_families", starter_families),
            # Branch conditions name the species the ROM itself compares, so the
            # resolver needs this profile's own species names.
            ("species_names", species_names),
            # Lets the resolver name an unguarded fallthrough branch's species
            # by elimination against the profile's own starter table, instead
            # of a generic "remaining starter" label.
            ("starter_species", starter_species),
        )
        if value is not None
    }
    return rematch_source, resolve_trainer_variants(
        cast(TrainerVariantResolver, engine),
        profile.id,
        profile.parameters,
        records,
        selector_data or None,
    )


def _class_gender_source(
    layout: _ClassGenderLayout, prize_table: _ClassPrizeTable, class_count: int
) -> dict[str, Any]:
    return {
        "trainer_archive": layout.trainer_path,
        "party_archive": layout.party_path,
        "trainer_names": {
            "archive": layout.messages_path,
            "member": layout.names_member,
        },
        "trainer_classes": {
            "archive": layout.messages_path,
            "member": layout.classes_member,
        },
        "trainer_class_genders": {
            "arm9_offset": layout.class_gender_offset,
            "count": class_count,
        },
        "trainer_class_prize_multipliers": (
            {
                "overlay_id": prize_table.overlay_id,
                "offset": prize_table.offset,
                "count": len(prize_table.multipliers),
            }
            if prize_table.multipliers is not None
            else None
        ),
    }


def _extract_class_gender_trainer_locations(
    engine: TrainerConcern,
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
    int,
]:
    assert result.match is not None
    profile = result.match.profile
    capabilities = get_engine(profile.engine).capabilities
    if TRAINER_LOCATIONS not in capabilities:
        return {}, {}, {"trainer_locations": "unsupported"}, 0
    layout = _read_trainer_location_layout(profile, engine)

    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=layout.map_names_path,
        table_offset=layout.table_offset,
        count=layout.count,
        location_names_member=layout.location_names_member,
    )
    events, scripts = _open_trainer_location_archives(
        profile,
        platform,
        filesystem,
        layout,
        extract_script_references=TRAINER_SCRIPT_REFERENCES in capabilities,
    )
    object_cache: dict[int, tuple[Any, ...]] = {}
    script_cache: dict[int, tuple[Any, ...]] = {}
    locations: dict[int, list[TrainerLocation]] = {}
    script_references: dict[int, list[TrainerScriptReference]] = {}
    unresolved_trainer_location_count = 0

    for header in headers:
        objects = _header_object_events(engine, events, object_cache, header, layout)
        for object_event in objects:
            # `trainer_type != 0` is exactly `is_trainer_object_candidate`'s own
            # check -- an object past this gate is already a confirmed
            # candidate, so a script_id outside the trainer-object range below
            # is a real unresolved trainer placement, not a shape mismatch.
            if object_event.trainer_type == 0:
                continue
            if not layout.script_start <= object_event.script_id <= layout.script_end:
                unresolved_trainer_location_count += 1
                continue
            trainer_id = _object_trainer_id(
                object_event, header, layout, trainer_count=trainer_count
            )
            locations.setdefault(trainer_id, []).append(
                _trainer_location(header, object_event, location_names)
            )
        if scripts is None:
            continue
        if header.script_file_id not in script_cache:
            script_cache[header.script_file_id] = _script_battle_commands(
                engine,
                scripts,
                header,
                trainer_count=trainer_count,
                tag_battles=TAG_BATTLES in capabilities,
            )
        for trainer_id, reference in _script_trainer_references(
            header, script_cache[header.script_file_id], location_names
        ):
            script_references.setdefault(trainer_id, []).append(reference)
    return (
        locations,
        script_references,
        _trainer_location_source(
            engine, layout, extract_script_references=scripts is not None
        ),
        unresolved_trainer_location_count,
    )


def _read_trainer_location_layout(
    profile: Any, engine: TrainerConcern
) -> _TrainerLocationLayout:
    parameters = profile.parameters
    try:
        events_path = profile.layout["events"]
        scripts_path = profile.layout["scripts"]
        map_names_path = profile.layout["map_names"]
        count = parameters["map_header_count"]
        table_offset = parameters["map_header_offset"]
        location_names_member = parameters["location_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer location metadata: {error.args[0]}"
        ) from error
    return _TrainerLocationLayout(
        events_path=events_path,
        scripts_path=scripts_path,
        map_names_path=map_names_path,
        count=count,
        table_offset=table_offset,
        location_names_member=location_names_member,
        null_event_id=parameters.get("null_event_id", engine.ARCHIVE_MEMBER_NONE),
        script_start=parameters.get(
            "trainer_script_start", engine.TRAINER_OBJECT_SCRIPT_START
        ),
        script_end=parameters.get(
            "trainer_script_end", engine.TRAINER_OBJECT_SCRIPT_END
        ),
        trainer_id_offset=parameters.get(
            "trainer_script_id_offset", engine.TRAINER_OBJECT_ID_OFFSET
        ),
    )


def _open_trainer_location_archives(
    profile: Any,
    platform: Any,
    filesystem: Any,
    layout: _TrainerLocationLayout,
    *,
    extract_script_references: bool,
) -> tuple[Any, Any | None]:
    event_options = {}
    if profile.parameters.get("events_allow_incorrect_data_block_size", False):
        event_options["allow_incorrect_data_block_size"] = True
    events = platform.archive_cls.from_bytes(
        filesystem.read(layout.events_path), **event_options
    )
    scripts = (
        platform.archive_cls.from_bytes(
            filesystem.read(layout.scripts_path), **scripts_archive_options(profile)
        )
        if extract_script_references
        else None
    )
    return events, scripts


def _header_object_events(
    engine: TrainerConcern,
    events: Any,
    object_cache: dict[int, tuple[Any, ...]],
    header: Any,
    layout: _TrainerLocationLayout,
) -> tuple[Any, ...]:
    if header.event_file_id == layout.null_event_id:
        return ()
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
    return object_cache[header.event_file_id]


def _object_trainer_id(
    object_event: Any,
    header: Any,
    layout: _TrainerLocationLayout,
    *,
    trainer_count: int,
) -> int:
    trainer_id = object_event.script_id - layout.script_start + layout.trainer_id_offset
    if not 0 <= trainer_id < trainer_count:
        raise InvalidRomError(
            f"Trainer object in map header {header.header_id} resolves to "
            f"missing trainer {trainer_id}"
        )
    return trainer_id


def _trainer_location(
    header: Any, object_event: Any, location_names: tuple[str, ...]
) -> TrainerLocation:
    return TrainerLocation(
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


def _script_battle_commands(
    engine: TrainerConcern,
    scripts: Any,
    header: Any,
    *,
    trainer_count: int,
    tag_battles: bool,
) -> tuple[Any, ...]:
    if header.script_file_id >= len(scripts.members):
        raise InvalidRomError(
            f"Map header {header.header_id} references missing script file "
            f"{header.script_file_id}"
        )
    script_data = scripts.read(header.script_file_id)
    commands = list(
        engine.parse_trainer_battle_commands(script_data, trainer_count=trainer_count)
    )
    # Optional: a second, differently-shaped battle command some
    # profiles use (Platinum's tag battles) that the shared scanner
    # above doesn't recognize. Its resolved trainer_ids may include
    # a tag-battle partner alongside the two real opponents; that
    # partner still genuinely appears at this location, even though
    # labeling it an "opponent slot" below is an approximation this
    # schema has no separate concept for.
    if tag_battles:
        commands.extend(
            engine.parse_tag_battle_commands(script_data, trainer_count=trainer_count)
        )
    return tuple(commands)


def _script_trainer_references(
    header: Any, commands: tuple[Any, ...], location_names: tuple[str, ...]
) -> Iterator[tuple[int, TrainerScriptReference]]:
    for command in commands:
        for opponent_slot, trainer_id in enumerate(command.trainer_ids, start=1):
            yield (
                trainer_id,
                TrainerScriptReference(
                    header_id=header.header_id,
                    internal_name=header.internal_name,
                    location_name_id=header.location_name_id,
                    name=location_names[header.location_name_id],
                    script_file_id=header.script_file_id,
                    command_offset=command.offset,
                    opponent_slot=opponent_slot,
                ),
            )


def _trainer_location_source(
    engine: TrainerConcern,
    layout: _TrainerLocationLayout,
    *,
    extract_script_references: bool,
) -> dict[str, Any]:
    return {
        "trainer_locations": {
            "events_archive": layout.events_path,
            "map_headers": {"arm9_offset": layout.table_offset, "count": layout.count},
            "internal_names": layout.map_names_path,
            "location_names_member": layout.location_names_member,
            "script_range": [layout.script_start, layout.script_end],
            "trainer_id_offset": layout.trainer_id_offset,
        },
        "trainer_script_references": {
            "scripts_archive": layout.scripts_path,
            "start_trainer_battle_opcode": engine.START_TRAINER_BATTLE,
            "check_won_battle_opcode": engine.CHECK_WON_BATTLE,
            "literal_ids_only": True,
        }
        if extract_script_references
        else "unsupported",
    }
