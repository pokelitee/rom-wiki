from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from romwiki.engines.concerns import TutorConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    iter_segment_map_headers,
    parse_map_header_table,
    read_code_binary,
    read_region_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import TUTORS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


@dataclass(frozen=True)
class _SpecialTutorSource:
    scripts: Any
    headers: Any
    location_names: tuple[str, ...]
    personal_records: dict[int, Any]
    minimum_friendship: int


def extract_tutor_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for tutor extraction")
    profile = result.match.profile
    tutor_format = get_engine(profile.engine).formats.tutors
    if tutor_format == "personal-archive":
        return _extract_personal_archive_tutors(result)
    if tutor_format == "overlay-archive":
        return _extract_overlay_archive_tutors(result)
    if tutor_format == "flat-offset-table":
        return _extract_flat_offset_tutors(result)
    if tutor_format != "overlay-table":
        raise DataSourceError(
            f"Engine {profile.engine!r} does not provide tutor extraction"
        )
    return _extract_overlay_table_tutors(result)


def _extract_overlay_table_tutors(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    required = (
        "tutor_overlay_id",
        "tutor_move_offset",
        "tutor_count",
        "tutor_compatibility_offset",
    )
    try:
        parameters = {name: profile.parameters[name] for name in required}
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define tutor data"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).tutors
    if platform.read_overlay is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    overlay, data = platform.read_overlay(result.image, parameters["tutor_overlay_id"])
    move_size = parameters["tutor_count"] * engine.TUTOR_RECORD_SIZE
    form_members = tuple(sorted(engine.FORM_MEMBERS))
    compatibility_count = engine.BASE_SPECIES_COUNT + len(form_members)
    compatibility_size = compatibility_count * engine.TUTOR_COMPATIBILITY_RECORD_SIZE
    move_data = _slice_overlay(data, parameters["tutor_move_offset"], move_size, "move")
    compatibility_data = _slice_overlay(
        data,
        parameters["tutor_compatibility_offset"],
        compatibility_size,
        "compatibility",
    )
    tutors = engine.parse_tutor_move_table(
        move_data, tutor_count=parameters["tutor_count"]
    )
    location_names = list(engine.TUTOR_LOCATION_NAMES)
    if any(tutor.location_id >= len(location_names) for tutor in tutors):
        raise InvalidRomError("Gen IV tutor references an unknown location ID")

    compatibility = engine.parse_tutor_compatibility_table(
        compatibility_data,
        tutor_count=parameters["tutor_count"],
        base_species_count=engine.BASE_SPECIES_COUNT,
        form_member_start=form_members[0],
        form_count=len(form_members),
    )
    special_tutors, special_compatibility = _extract_special_tutors(
        engine,
        platform,
        result,
        start_tutor_id=len(tutors) + 1,
    )
    envelope = dataset_envelope(
        schema_version=TUTORS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="move_tutors",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": parameters["tutor_move_offset"],
            "compatibility_offset": parameters["tutor_compatibility_offset"],
        },
        records=[{**tutor.to_dict(), "kind": "shard"} for tutor in tutors],
    )
    envelope["compatibility_record_count"] = len(compatibility)
    envelope["special_record_count"] = len(special_tutors)
    envelope["special_compatibility_record_count"] = len(special_compatibility)
    envelope["location_names"] = location_names
    envelope["compatibility"] = [record.to_dict() for record in compatibility]
    envelope["special_records"] = special_tutors
    envelope["special_compatibility"] = special_compatibility
    return envelope


def _extract_overlay_archive_tutors(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["tutor_overlay_id"]
        move_offset = profile.parameters["tutor_move_offset"]
        compatibility_path = profile.layout["tutor_compatibility"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing HGSS tutor metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).tutors
    if platform.read_overlay_decompressed is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    if platform.filesystem_from_image is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    overlay, overlay_data = platform.read_overlay_decompressed(result.image, overlay_id)
    move_size = engine.TUTOR_COUNT * engine.TUTOR_RECORD_SIZE
    move_data = _slice_overlay(overlay_data, move_offset, move_size, "move")
    tutors = engine.parse_tutor_move_table(move_data)

    filesystem = platform.filesystem_from_image(result.image)
    compatibility_data = filesystem.read(compatibility_path)
    form_members = tuple(sorted(engine.FORM_MEMBERS))
    compatibility = engine.parse_tutor_compatibility_table(
        compatibility_data,
        base_species_count=engine.BASE_SPECIES_COUNT,
        form_member_start=form_members[0],
        form_count=len(form_members),
    )
    envelope = dataset_envelope(
        schema_version=TUTORS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="move_tutors",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": move_offset,
            "compatibility_archive": compatibility_path,
        },
        records=[{**record.to_dict(), "kind": "battle-points"} for record in tutors],
    )
    envelope["compatibility_record_count"] = len(compatibility)
    envelope["special_record_count"] = 0
    envelope["special_compatibility_record_count"] = 0
    envelope["location_names"] = list(engine.TUTOR_LOCATION_NAMES)
    envelope["compatibility"] = [record.to_dict() for record in compatibility]
    envelope["special_records"] = []
    envelope["special_compatibility"] = []
    return envelope


def _extract_personal_archive_tutors(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["tutor_overlay_id"]
        move_offset = profile.parameters["tutor_move_offset"]
        personal_path = profile.layout["personal"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing B2W2 tutor metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).tutors
    if platform.read_overlay_decompressed is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    overlay, overlay_data = platform.read_overlay_decompressed(result.image, overlay_id)
    filesystem = platform.filesystem_from_image(result.image)
    personal = platform.archive_cls.from_bytes(filesystem.read(personal_path))
    move_size = engine.TUTOR_COUNT * engine.TUTOR_RECORD_SIZE
    move_data = _slice_overlay(overlay_data, move_offset, move_size, "move")
    records = [
        {**record.to_dict(), "kind": "shard"}
        for record in engine.parse_tutor_move_table(move_data)
    ]
    compatibility = []
    for member in (
        *range(1, engine.BASE_SPECIES_COUNT + 1),
        *sorted(engine.FORM_MEMBERS),
    ):
        compatibility.append(
            engine.parse_tutor_compatibility_record(
                personal.read(member), personal_member=member
            ).to_dict()
        )
    envelope = dataset_envelope(
        schema_version=TUTORS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="move_tutors",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": move_offset,
            "compatibility_archive": personal_path,
            "compatibility_offset": engine.TUTOR_COMPATIBILITY_OFFSET,
        },
        records=records,
    )
    envelope["compatibility_record_count"] = len(compatibility)
    envelope["special_record_count"] = 0
    envelope["special_compatibility_record_count"] = 0
    envelope["location_names"] = list(engine.TUTOR_LOCATION_NAMES)
    envelope["compatibility"] = compatibility
    envelope["special_records"] = []
    envelope["special_compatibility"] = []
    return envelope


def _slice_overlay(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError(f"Gen IV tutor {label} table is outside its overlay")
    return data[offset : offset + size]


def _extract_special_tutors(
    engine: TutorConcern,
    platform: Any,
    result: InspectionResult,
    *,
    start_tutor_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assert result.match is not None
    profile = result.match.profile
    definitions = profile.parameters.get("special_tutors", [])
    if not isinstance(definitions, list):
        raise ProfileError("Special tutor definitions must be a list")
    if not definitions:
        return [], []
    source = _load_special_tutor_source(engine, platform, result)

    records = []
    compatibility: dict[int, list[int]] = {}
    for index, definition in enumerate(definitions):
        tutor_id = start_tutor_id + index
        tutor, eligibility_kind, eligibility_value = _decode_special_tutor(
            engine, source, definition, tutor_id=tutor_id
        )
        records.append({**tutor.to_dict(), "kind": "special"})
        for member, personal_record in source.personal_records.items():
            eligible = (
                member in eligibility_value
                if eligibility_kind == "species"
                else eligibility_value in personal_record.type_ids
            )
            if eligible:
                compatibility.setdefault(member, []).append(tutor_id)

    return records, [
        {"personal_member": member, "tutor_ids": tutor_ids}
        for member, tutor_ids in sorted(compatibility.items())
    ]


def _load_special_tutor_source(
    engine: TutorConcern, platform: Any, result: InspectionResult
) -> _SpecialTutorSource:
    assert result.match is not None
    profile = result.match.profile
    try:
        minimum_friendship = profile.int_parameter(
            "special_tutor_minimum_friendship", engine.MAX_FRIENDSHIP
        )
        script_path = profile.layout["scripts"]
        personal_path = profile.layout["personal"]
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        location_names_member = profile.parameters["location_names_member"]
        map_header_offset = profile.parameters["map_header_offset"]
        map_header_count = profile.parameters["map_header_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing special tutor metadata: {error.args[0]}"
        ) from error

    filesystem = platform.filesystem_from_image(result.image)
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(script_path), allow_truncated=True
    )
    personal = platform.archive_cls.from_bytes(filesystem.read(personal_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    location_names = engine.parse_english_message_archive(
        messages.read(location_names_member)
    )
    arm9_data = read_code_binary(platform, result.image)
    headers = parse_map_header_table(
        engine,
        arm9_data,
        filesystem,
        map_names_path,
        table_offset=map_header_offset,
        count=map_header_count,
    )
    public_members = tuple(range(1, engine.BASE_SPECIES_COUNT + 1)) + tuple(
        engine.FORM_MEMBERS
    )
    return _SpecialTutorSource(
        scripts=scripts,
        headers=headers,
        location_names=location_names,
        personal_records={
            member: engine.parse_personal_record(
                personal.read(member), species_id=member, archive_path=personal_path
            )
            for member in public_members
        },
        minimum_friendship=minimum_friendship,
    )


def _decode_special_tutor(
    engine: TutorConcern,
    source: _SpecialTutorSource,
    definition: Any,
    *,
    tutor_id: int,
) -> tuple[Any, str, Any]:
    try:
        script_member = definition["script_member"]
        command_offset = definition["command_offset"]
        map_header_id = definition["map_header_id"]
        eligibility_kind = definition["eligibility_kind"]
    except (KeyError, TypeError) as error:
        raise ProfileError("Special tutor definition is incomplete") from error
    if not 0 <= script_member < len(source.scripts.members):
        raise ProfileError("Special tutor references an unknown script member")
    if not 0 <= map_header_id < len(source.headers):
        raise ProfileError("Special tutor references an unknown map header")
    if source.headers[map_header_id].script_file_id != script_member:
        raise InvalidRomError(
            f"Special tutor map header {map_header_id} does not reference "
            f"script member {script_member}"
        )
    location_name_id = source.headers[map_header_id].location_name_id
    if location_name_id >= len(source.location_names):
        raise InvalidRomError(
            f"Special tutor map header {map_header_id} references missing "
            f"location name {location_name_id}"
        )
    script_data = source.scripts.read(script_member)
    eligibility_value = _special_tutor_eligibility_value(
        engine, definition, eligibility_kind, script_data
    )
    tutor = engine.parse_special_tutor_move(
        script_data,
        tutor_id=tutor_id,
        script_member=script_member,
        command_offset=command_offset,
        map_header_id=map_header_id,
        location_name=source.location_names[location_name_id],
        eligibility_kind=eligibility_kind,
        eligibility_value=eligibility_value,
        minimum_friendship=source.minimum_friendship,
    )
    return tutor, eligibility_kind, eligibility_value


def _special_tutor_eligibility_value(
    engine: TutorConcern, definition: Any, eligibility_kind: str, script_data: bytes
) -> Any:
    if eligibility_kind == "species":
        try:
            return engine.parse_special_tutor_species(
                script_data,
                comparison_offset=definition["comparison_offset"],
                species_count=definition["species_count"],
            )
        except KeyError as error:
            raise ProfileError(
                "Species-based special tutor definition is incomplete"
            ) from error
    if eligibility_kind == "type":
        try:
            return definition["eligibility_value"]
        except KeyError as error:
            raise ProfileError(
                "Type-based special tutor definition is incomplete"
            ) from error
    raise ProfileError("Special tutor eligibility kind is unknown")


def _extract_flat_offset_tutors(result: InspectionResult) -> dict[str, Any]:
    # Generation III's move tutors are individual overworld NPC scripts,
    # not a location-annotated data table -- only the 4 tutors with a
    # real, ROM-verified NPC location are exposed at all (see
    # `engines/gen3/frlg/constants.py`'s `TUTOR_LOCATIONS` comment).
    # `location_names` reuses the same Sevii Islands/postgame
    # `map_header_segments` decode `locations.py`'s own extraction and
    # `encounters.py`/`trainers/pointer_party.py`'s location backfills
    # already do. `TUTOR_LOCATIONS` names a target *region*, not a
    # `header_id` -- resolved against this specific ROM's own decoded
    # `location_names` below, since `header_id` numbering isn't guaranteed
    # stable across profiles (see that constant's comment).
    assert result.match is not None
    profile = result.match.profile
    try:
        move_offset = profile.parameters["tutor_move_offset"]
        compatibility_offset = profile.parameters["tutor_compatibility_offset"]
        personal_count = profile.parameters["personal_count"]
        segments = profile.parameters["map_header_segments"]
        region_name_offset = profile.parameters["region_name_offset"]
        region_name_count = profile.parameters["region_name_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define tutor_move_offset/"
            "tutor_compatibility_offset/map_header_segments/region_name_offset/"
            "region_name_count"
        ) from error

    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).tutors

    region_names = read_region_names(
        engine,
        platform,
        result.image,
        offset=region_name_offset,
        count=region_name_count,
    )
    location_names = [
        header.name
        for header in iter_segment_map_headers(
            engine, platform, result.image, segments, region_names
        )
    ]
    location_ids = _resolve_tutor_location_ids(engine, location_names)
    move_data = platform.read_bytes(
        result.image, move_offset, engine.TUTOR_MOVE_COUNT * 2
    )
    tutors = engine.parse_tutor_move_table(move_data, location_ids=location_ids)
    compatibility = _decode_flat_tutor_compatibility(
        engine, platform, result.image, compatibility_offset, personal_count
    )

    envelope = dataset_envelope(
        schema_version=TUTORS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="move_tutors",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "move_offset": move_offset,
            "compatibility_offset": compatibility_offset,
        },
        records=[{**tutor.to_dict(), "kind": "shard"} for tutor in tutors],
    )
    envelope["compatibility_record_count"] = len(compatibility)
    envelope["special_record_count"] = 0
    envelope["special_compatibility_record_count"] = 0
    envelope["location_names"] = location_names
    envelope["compatibility"] = [record.to_dict() for record in compatibility]
    envelope["special_records"] = []
    envelope["special_compatibility"] = []
    return envelope


def _resolve_tutor_location_ids(
    engine: TutorConcern, location_names: list[str]
) -> dict[int, int]:
    location_ids = {}
    for table_index, target_name in engine.TUTOR_LOCATIONS.items():
        try:
            location_ids[table_index] = location_names.index(target_name)
        except ValueError as error:
            raise InvalidRomError(
                f"Gen III tutor {table_index} references location "
                f"{target_name!r}, not present in this ROM's decoded locations"
            ) from error
    return location_ids


def _decode_flat_tutor_compatibility(
    engine: TutorConcern,
    platform: Any,
    image: Any,
    compatibility_offset: int,
    personal_count: int,
) -> list[Any]:
    compatibility_data = platform.read_bytes(
        image, compatibility_offset, personal_count * 2
    )
    # Bounded to the engine's exposed species count, not the table's real
    # on-ROM size -- the same "populate what's real and currently exposed"
    # gap `egg_moves.py`'s padding-species filter documents.
    decoded_species_count = min(personal_count, engine.PERSONAL_RECORD_COUNT)
    return [
        record
        for species_id in range(decoded_species_count)
        if (
            record := engine.parse_tutor_compatibility(
                compatibility_data[species_id * 2 : species_id * 2 + 2],
                species_id=species_id,
                table_index=species_id,
            )
        )
        is not None
    ]
