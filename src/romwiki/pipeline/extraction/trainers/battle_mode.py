from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any, cast

from romwiki.engines.concerns import TrainerConcern
from romwiki.engines.registry import DIFFICULTY_BRANCHES, get_engine
from romwiki.engines.trainer_variants import (
    TrainerVariantResolver,
    resolve_trainer_variants,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.extraction.trainers.support import (
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


@dataclass(frozen=True)
class _BattleModeMapSource:
    scripts_path: str
    overworld_objects_path: str
    headers: tuple[Any, ...]
    script_file_ids: tuple[int, ...]
    scripts: Any
    overworld_objects: Any
    unused_overworld_members: frozenset[int]


def extract_battle_mode_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    # This generation's trainer/party record shape is close enough to Gen
    # IV's to reuse the same schema-level idea (header + party array with
    # optional held-item/custom-move blocks). Member 0 of both archives is an
    # unused, differently-shaped placeholder (confirmed against real ROM
    # data: 16 bytes vs. the normal 20, 6 bytes vs. a real party record), so
    # real trainer IDs start at 1. The owning engine leaf resolves the
    # message-table index: BW omits entry zero, while B2W2 retains it.
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

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).trainers
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    parsed_records, reference_names = _decode_battle_mode_trainer_records(
        profile,
        engine,
        platform,
        filesystem,
        messages,
        trainer_path=trainer_path,
        party_path=party_path,
        names_member=names_member,
        classes_member=classes_member,
    )
    trainer_count = len(parsed_records) + 1
    (
        locations_by_trainer,
        script_references_by_trainer,
        location_source,
        difficulty_branch_families,
    ) = _extract_battle_mode_trainer_locations(
        engine, platform, result, filesystem, trainer_count=trainer_count
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
    variant_contract = _resolve_battle_mode_variants(
        profile,
        platform,
        engine,
        result,
        filesystem,
        records,
        trainer_count=trainer_count,
        difficulty_branch_families=difficulty_branch_families,
        species_names=reference_names.get("pokemon_names"),
    )
    return _build_battle_mode_envelope(
        profile,
        {
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
            **location_source,
        },
        records,
        variant_contract=variant_contract,
        reference_names=reference_names,
    )


def _build_battle_mode_envelope(
    profile: Any,
    source: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    variant_contract: dict[str, Any],
    reference_names: dict[str, Any],
) -> dict[str, Any]:
    envelope = dataset_envelope(
        schema_version=TRAINERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="trainers",
        source=source,
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


def _decode_battle_mode_trainer_records(
    profile: Any,
    engine: TrainerConcern,
    platform: Any,
    filesystem: Any,
    messages: Any,
    *,
    trainer_path: str,
    party_path: str,
    names_member: int,
    classes_member: int,
) -> tuple[list[Any], dict[str, Any]]:
    trainers = platform.archive_cls.from_bytes(filesystem.read(trainer_path))
    parties = platform.archive_cls.from_bytes(filesystem.read(party_path))
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
    return parsed_records, reference_names


def _resolve_battle_mode_variants(
    profile: Any,
    platform: Any,
    engine: TrainerConcern,
    result: InspectionResult,
    filesystem: Any,
    records: list[dict[str, Any]],
    *,
    trainer_count: int,
    difficulty_branch_families: tuple[Any, ...],
    species_names: Any,
) -> dict[str, Any]:
    starter_species = read_starter_species(profile, platform, engine, result)
    starter_families = read_starter_branch_families(
        profile,
        platform,
        engine,
        filesystem,
        trainer_count=trainer_count,
        starter_species=starter_species,
    )
    selector_data = {
        key: value
        for key, value in (
            ("starter_branch_families", starter_families),
            ("difficulty_branch_families", difficulty_branch_families),
            ("starter_species", starter_species),
            ("species_names", species_names),
        )
        if value is not None
    }
    return resolve_trainer_variants(
        cast(TrainerVariantResolver, engine),
        profile.id,
        profile.parameters,
        records,
        selector_data or None,
    )


def _extract_battle_mode_trainer_locations(
    engine: TrainerConcern,
    platform: Any,
    result: InspectionResult,
    filesystem: Any,
    *,
    trainer_count: int,
) -> tuple[
    dict[int, list[TrainerLocation]],
    dict[int, list[TrainerScriptReference]],
    dict[str, Any],
    tuple[Any, ...],
]:
    """Resolve Gen5 trainer battle triggers' map locations.

    Two independent, literal-fact-only mechanisms (see
    `gen5/shared/overworld.py` and `gen5/bw/scripts.py` for the full verification
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
    source = _load_battle_mode_map_source(profile, engine, platform, filesystem)
    if source is None:
        return {}, {}, {}, ()

    locations: dict[int, list[TrainerLocation]] = {}
    script_references: dict[int, list[TrainerScriptReference]] = {}
    script_command_cache: dict[int, tuple[Any, ...]] = {}
    difficulty_branch_families = []
    has_difficulty_branches = (
        DIFFICULTY_BRANCHES in get_engine(profile.engine).capabilities
    )

    for header in source.headers:
        for trainer_id, location in _overworld_trainer_locations(
            engine, source, header, trainer_count=trainer_count
        ):
            locations.setdefault(trainer_id, []).append(location)

        script_file_id = source.script_file_ids[header.header_id]
        if script_file_id >= len(source.scripts.members):
            continue
        if script_file_id not in script_command_cache:
            script_data = source.scripts.read(script_file_id)
            script_command_cache[script_file_id] = engine.parse_trainer_battle_commands(
                script_data, trainer_count=trainer_count
            )
            if has_difficulty_branches:
                difficulty_branch_families.extend(
                    engine.parse_difficulty_branch_families(
                        script_data,
                        script_file_id=script_file_id,
                        trainer_count=trainer_count,
                    )
                )
        for trainer_id, reference in _script_trainer_references(
            header, script_file_id, script_command_cache[script_file_id]
        ):
            script_references.setdefault(trainer_id, []).append(reference)

    return (
        locations,
        script_references,
        {
            "trainer_locations": {
                "overworld_objects_archive": source.overworld_objects_path,
                "common_script_band_size": 1000,
            },
            "trainer_script_references": {
                "scripts_archive": source.scripts_path,
                "literal_ids_only": True,
            },
        },
        tuple(difficulty_branch_families),
    )


def _load_battle_mode_map_source(
    profile: Any, engine: TrainerConcern, platform: Any, filesystem: Any
) -> _BattleModeMapSource | None:
    required_layout = (
        "map_headers",
        "scripts",
        "overworld_objects",
        "messages",
    )
    if any(name not in profile.layout for name in required_layout) or (
        "map_names_member" not in profile.parameters
    ):
        return None
    map_headers_path = profile.layout["map_headers"]
    scripts_path = profile.layout["scripts"]
    overworld_objects_path = profile.layout["overworld_objects"]

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
    messages = platform.archive_cls.from_bytes(
        filesystem.read(profile.layout["messages"])
    )
    map_names = engine.parse_english_message_archive(
        messages.read(profile.parameters["map_names_member"])
    )
    headers = engine.parse_map_header_table(
        map_headers_data, map_names=tuple(map_names), archive_path=map_headers_path
    )
    script_file_ids = engine.parse_map_header_script_files(map_headers_data)

    field_archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        field_archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        field_archive_options["allow_trailing_data"] = True
    return _BattleModeMapSource(
        scripts_path=scripts_path,
        overworld_objects_path=overworld_objects_path,
        headers=headers,
        script_file_ids=script_file_ids,
        scripts=platform.archive_cls.from_bytes(
            filesystem.read(scripts_path),
            allow_truncated=True,
            **field_archive_options,
        ),
        overworld_objects=platform.archive_cls.from_bytes(
            filesystem.read(overworld_objects_path), **field_archive_options
        ),
        unused_overworld_members=frozenset(
            profile.parameters.get("overworld_objects_unused", ())
        ),
    )


def _overworld_trainer_locations(
    engine: TrainerConcern,
    source: _BattleModeMapSource,
    header: Any,
    *,
    trainer_count: int,
) -> Iterator[tuple[int, TrainerLocation]]:
    overworld_file_id = header.overworld_file_id
    if (
        overworld_file_id >= len(source.overworld_objects.members)
        or overworld_file_id in source.unused_overworld_members
    ):
        return
    npcs = engine.parse_overworld_npcs(source.overworld_objects.read(overworld_file_id))
    for npc in npcs:
        trainer_id = engine.resolve_common_script_trainer_id(
            npc.script_used, trainer_count=trainer_count
        )
        if trainer_id is None:
            continue
        yield (
            trainer_id,
            TrainerLocation(
                header_id=header.header_id,
                internal_name=f"map_{header.header_id}",
                location_name_id=header.header_id,
                name=header.name,
                event_file_id=overworld_file_id,
                object_index=npc.index,
                object_local_id=npc.index,
                script_id=npc.script_used,
                trainer_type=1,
                x=npc.x,
                y=npc.y,
                z=npc.z,
            ),
        )


def _script_trainer_references(
    header: Any, script_file_id: int, commands: tuple[Any, ...]
) -> Iterator[tuple[int, TrainerScriptReference]]:
    for command in commands:
        for opponent_slot, trainer_id in enumerate(command.trainer_ids, start=1):
            yield (
                trainer_id,
                TrainerScriptReference(
                    header_id=header.header_id,
                    internal_name=f"map_{header.header_id}",
                    location_name_id=header.header_id,
                    name=header.name,
                    script_file_id=script_file_id,
                    command_offset=command.offset,
                    opponent_slot=opponent_slot,
                ),
            )
