from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    parse_map_header_table,
    read_code_binary,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import TUTORS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


def extract_tutor_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for tutor extraction")
    profile = result.match.profile
    tutor_format = get_engine(profile.engine).formats.tutors
    if tutor_format == "personal-archive":
        return _extract_personal_archive_tutors(result)
    if tutor_format == "overlay-archive":
        return _extract_overlay_archive_tutors(result)
    if tutor_format != "overlay-table":
        raise DataSourceError(
            f"Engine {profile.engine!r} does not provide tutor extraction"
        )
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
    return {
        "schema_version": TUTORS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "move_tutors",
        "record_count": len(tutors),
        "compatibility_record_count": len(compatibility),
        "special_record_count": len(special_tutors),
        "special_compatibility_record_count": len(special_compatibility),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": parameters["tutor_move_offset"],
            "compatibility_offset": parameters["tutor_compatibility_offset"],
        },
        "location_names": location_names,
        "records": [{**tutor.to_dict(), "kind": "shard"} for tutor in tutors],
        "compatibility": [record.to_dict() for record in compatibility],
        "special_records": special_tutors,
        "special_compatibility": special_compatibility,
    }


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
    return {
        "schema_version": TUTORS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "move_tutors",
        "record_count": len(tutors),
        "compatibility_record_count": len(compatibility),
        "special_record_count": 0,
        "special_compatibility_record_count": 0,
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": move_offset,
            "compatibility_archive": compatibility_path,
        },
        "location_names": list(engine.TUTOR_LOCATION_NAMES),
        "records": [{**record.to_dict(), "kind": "battle-points"} for record in tutors],
        "compatibility": [record.to_dict() for record in compatibility],
        "special_records": [],
        "special_compatibility": [],
    }


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
    return {
        "schema_version": TUTORS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "move_tutors",
        "record_count": len(records),
        "compatibility_record_count": len(compatibility),
        "special_record_count": 0,
        "special_compatibility_record_count": 0,
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": move_offset,
            "compatibility_archive": personal_path,
            "compatibility_offset": engine.TUTOR_COMPATIBILITY_OFFSET,
        },
        "location_names": list(engine.TUTOR_LOCATION_NAMES),
        "records": records,
        "compatibility": compatibility,
        "special_records": [],
        "special_compatibility": [],
    }


def _slice_overlay(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError(f"Gen IV tutor {label} table is outside its overlay")
    return data[offset : offset + size]


def _extract_special_tutors(
    engine: Any, platform: Any, result: InspectionResult, *, start_tutor_id: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assert result.match is not None
    profile = result.match.profile
    definitions = profile.parameters.get("special_tutors", [])
    if not isinstance(definitions, list):
        raise ProfileError("Special tutor definitions must be a list")
    if not definitions:
        return [], []
    try:
        minimum_friendship = profile.parameters.get(
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

    records = []
    compatibility: dict[int, list[int]] = {}
    public_members = tuple(range(1, engine.BASE_SPECIES_COUNT + 1)) + tuple(
        engine.FORM_MEMBERS
    )
    personal_records = {
        member: engine.parse_personal_record(
            personal.read(member), species_id=member, archive_path=personal_path
        )
        for member in public_members
    }
    for index, definition in enumerate(definitions):
        try:
            script_member = definition["script_member"]
            command_offset = definition["command_offset"]
            map_header_id = definition["map_header_id"]
            eligibility_kind = definition["eligibility_kind"]
        except (KeyError, TypeError) as error:
            raise ProfileError("Special tutor definition is incomplete") from error
        if not 0 <= script_member < len(scripts.members):
            raise ProfileError("Special tutor references an unknown script member")
        if not 0 <= map_header_id < len(headers):
            raise ProfileError("Special tutor references an unknown map header")
        if headers[map_header_id].script_file_id != script_member:
            raise InvalidRomError(
                f"Special tutor map header {map_header_id} does not reference "
                f"script member {script_member}"
            )
        location_name_id = headers[map_header_id].location_name_id
        if location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Special tutor map header {map_header_id} references missing "
                f"location name {location_name_id}"
            )
        location_name = location_names[location_name_id]
        script_data = scripts.read(script_member)
        if eligibility_kind == "species":
            try:
                eligibility_value = engine.parse_special_tutor_species(
                    script_data,
                    comparison_offset=definition["comparison_offset"],
                    species_count=definition["species_count"],
                )
            except KeyError as error:
                raise ProfileError(
                    "Species-based special tutor definition is incomplete"
                ) from error
        elif eligibility_kind == "type":
            try:
                eligibility_value = definition["eligibility_value"]
            except KeyError as error:
                raise ProfileError(
                    "Type-based special tutor definition is incomplete"
                ) from error
        else:
            raise ProfileError("Special tutor eligibility kind is unknown")

        tutor_id = start_tutor_id + index
        tutor = engine.parse_special_tutor_move(
            script_data,
            tutor_id=tutor_id,
            script_member=script_member,
            command_offset=command_offset,
            map_header_id=map_header_id,
            location_name=location_name,
            eligibility_kind=eligibility_kind,
            eligibility_value=eligibility_value,
            minimum_friendship=minimum_friendship,
        )
        records.append({**tutor.to_dict(), "kind": "special"})
        for member, personal_record in personal_records.items():
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
