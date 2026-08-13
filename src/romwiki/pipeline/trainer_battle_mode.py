from __future__ import annotations

from dataclasses import replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.engines.trainer_variants import resolve_trainer_variants
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.pipeline.trainer_extraction_support import (
    read_starter_branch_families,
    read_starter_species,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import TrainerLocation, TrainerScriptReference
from romwiki.schema.versions import (
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINERS_RAW_SCHEMA_VERSION,
)
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_battle_mode_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    # This generation's trainer/party record shape is close enough to Gen
    # IV's to reuse the same schema-level idea (header + party array with
    # optional held-item/custom-move blocks). Member 0 of both archives is an
    # unused, differently-shaped placeholder (confirmed against real ROM
    # data: 16 bytes vs. the normal 20, 6 bytes vs. a real party record), so
    # real trainer IDs start at 1. The owning engine leaf resolves the
    # message-table index: BW omits entry zero, while B2W2 retains it.
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
    name_indexes = {
        member.index: engine.trainer_name_index(member.index)
        for member in trainers.members
        if member.index != 0
    }
    if any(index < 0 or index >= len(names) for index in name_indexes.values()):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    parsed_records = [
        engine.parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[name_indexes[member.index]],
            class_names=classes,
            trainer_archive=trainer_path,
            party_archive=party_path,
        )
        for member in trainers.members
        if member.index != 0
    ]
    (
        locations_by_trainer,
        script_references_by_trainer,
        location_source,
    ) = _extract_battle_mode_trainer_locations(
        engine, platform, result, filesystem, trainer_count=len(parsed_records) + 1
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
    starter_species = read_starter_species(profile, platform, engine, result)
    starter_families = read_starter_branch_families(
        profile,
        platform,
        engine,
        filesystem,
        trainer_count=len(parsed_records) + 1,
        starter_species=starter_species,
    )
    selector_data = {
        key: value
        for key, value in (
            ("starter_branch_families", starter_families),
            ("starter_species", starter_species),
            ("species_names", reference_names.get("pokemon_names")),
        )
        if value is not None
    }
    variant_contract = resolve_trainer_variants(
        engine, profile.id, profile.parameters, records, selector_data or None
    )
    return {
        "schema_version": TRAINERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "trainers",
        "battle_family_schema_version": TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
        **variant_contract,
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
            **location_source,
        },
        **reference_names,
        "records": records,
    }


def _extract_battle_mode_trainer_locations(
    engine: Any,
    platform: Any,
    result: InspectionResult,
    filesystem: Any,
    *,
    trainer_count: int,
) -> tuple[
    dict[int, list[TrainerLocation]],
    dict[int, list[TrainerScriptReference]],
    dict[str, Any],
]:
    """Resolve Gen5 trainer battle triggers' map locations.

    Two independent, literal-fact-only mechanisms (see
    `gen5/bw/overworld.py` and `gen5/bw/scripts.py` for the full verification
    against real Black ROM data):

    - Sight-triggered ("walk into view") battles: each map's overworld NPC
      records (`layout.overworld_objects`) carry the trainer ID directly,
      encoded as `band + trainer_id` in the NPC's own `scriptUsed` field.
    - Talk-triggered/scripted battles: each map's own dedicated script file
      (`layout.map_headers`'s undecoded byte-6 field) is scanned for literal
      `CallTrainerBattle`/`CallTrainerMultiBattle` commands.

    Both intentionally skip battles whose trainer ID can't be resolved to a
    real trainer record rather than guessing.
    """
    assert result.match is not None
    profile = result.match.profile
    required_layout = (
        "map_headers",
        "scripts",
        "overworld_objects",
        "messages",
    )
    if any(name not in profile.layout for name in required_layout) or (
        "map_names_member" not in profile.parameters
    ):
        return {}, {}, {}
    map_headers_path = profile.layout["map_headers"]
    scripts_path = profile.layout["scripts"]
    overworld_objects_path = profile.layout["overworld_objects"]
    messages_path = profile.layout["messages"]
    map_names_member = profile.parameters["map_names_member"]

    map_headers_archive = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    map_headers_data = map_headers_archive.read(0)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    headers = engine.parse_map_header_table(
        map_headers_data, map_names=tuple(map_names), archive_path=map_headers_path
    )
    script_file_ids = engine.parse_map_header_script_files(map_headers_data)

    field_archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        field_archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        field_archive_options["allow_trailing_data"] = True
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path),
        allow_truncated=True,
        **field_archive_options,
    )
    overworld_objects = platform.archive_cls.from_bytes(
        filesystem.read(overworld_objects_path), **field_archive_options
    )
    unused_overworld_members = frozenset(
        profile.parameters.get("overworld_objects_unused", ())
    )

    locations: dict[int, list[TrainerLocation]] = {}
    script_references: dict[int, list[TrainerScriptReference]] = {}
    script_command_cache: dict[int, tuple[Any, ...]] = {}

    for header in headers:
        header_id = header.header_id
        internal_name = f"map_{header_id}"

        if (
            header_id < len(overworld_objects.members)
            and header_id not in unused_overworld_members
        ):
            npcs = engine.parse_overworld_npcs(overworld_objects.read(header_id))
            for npc in npcs:
                trainer_id = engine.resolve_common_script_trainer_id(
                    npc.script_used, trainer_count=trainer_count
                )
                if trainer_id is None:
                    continue
                locations.setdefault(trainer_id, []).append(
                    TrainerLocation(
                        header_id=header_id,
                        internal_name=internal_name,
                        location_name_id=header_id,
                        name=header.name,
                        event_file_id=header_id,
                        object_index=npc.index,
                        object_local_id=npc.index,
                        script_id=npc.script_used,
                        trainer_type=1,
                        x=npc.x,
                        y=npc.y,
                        z=npc.z,
                    )
                )

        script_file_id = script_file_ids[header_id]
        if script_file_id >= len(scripts.members):
            continue
        if script_file_id not in script_command_cache:
            script_command_cache[script_file_id] = engine.parse_trainer_battle_commands(
                scripts.read(script_file_id), trainer_count=trainer_count
            )
        for command in script_command_cache[script_file_id]:
            for opponent_slot, trainer_id in enumerate(command.trainer_ids, start=1):
                script_references.setdefault(trainer_id, []).append(
                    TrainerScriptReference(
                        header_id=header_id,
                        internal_name=internal_name,
                        location_name_id=header_id,
                        name=header.name,
                        script_file_id=script_file_id,
                        command_offset=command.offset,
                        opponent_slot=opponent_slot,
                    )
                )

    return (
        locations,
        script_references,
        {
            "trainer_locations": {
                "overworld_objects_archive": overworld_objects_path,
                "common_script_band_size": 1000,
            },
            "trainer_script_references": {
                "scripts_archive": scripts_path,
                "literal_ids_only": True,
            },
        },
    )
