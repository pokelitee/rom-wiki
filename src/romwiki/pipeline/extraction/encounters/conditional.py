from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from romwiki.engines.concerns import EncounterConcern
from romwiki.engines.registry import COMPRESSED_CODE_BINARY, get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.semantics.encounter_identity import EncounterSourceType
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.encounters import EncounterLocation
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_conditional_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        archive_path = profile.layout["encounters"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define an encounter archive"
        ) from error

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).encounters
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(
        filesystem.read(archive_path),
        allow_truncated=profile.parameters.get("encounters_allow_truncated", False),
        allow_trailing_data=profile.parameters.get(
            "encounters_allow_trailing_data", False
        ),
    )
    reference_names = extract_reference_names(profile, filesystem)
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
    records.extend(
        _extract_headbutt_encounters(
            result,
            engine,
            platform,
            filesystem,
            first_area_id=len(records),
        )
    )
    records.extend(
        _extract_safari_encounters(
            result,
            engine,
            platform,
            filesystem,
            first_area_id=len(records),
        )
    )
    envelope = dataset_envelope(
        schema_version=ENCOUNTERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="wild_encounters",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
            **location_source,
        },
        records=records,
    )
    envelope.update(reference_names)
    return envelope


def _extract_headbutt_encounters(
    result: InspectionResult,
    engine: EncounterConcern,
    platform: Any,
    filesystem: Any,
    *,
    first_area_id: int,
) -> list[dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    archive_path = profile.layout.get("headbutt_encounters")
    if archive_path is None:
        return []
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    map_header_count = profile.int_parameter("map_header_count")
    if len(archive.members) != map_header_count:
        raise InvalidRomError(
            f"Headbutt archive has {len(archive.members)} members, expected "
            f"{map_header_count}"
        )

    messages = platform.archive_cls.from_bytes(
        filesystem.read(profile.layout["messages"]),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    headers, location_names = resolve_map_headers(
        engine,
        read_code_binary(
            platform,
            result.image,
            compressed=COMPRESSED_CODE_BINARY
            in get_engine(profile.engine).capabilities,
        ),
        filesystem,
        messages,
        map_names_path=profile.layout["map_names"],
        table_offset=profile.int_parameter("map_header_offset"),
        count=map_header_count,
        location_names_member=profile.int_parameter("location_names_member"),
    )
    records: list[dict[str, Any]] = []
    for member in archive.members:
        encounter = engine.parse_headbutt_record(
            archive.read(member.index),
            header_id=member.index,
            archive_path=archive_path,
            species_count=engine.POKEMON_NAME_COUNT,
        )
        if encounter is None:
            continue
        header = headers[member.index]
        records.append(
            {
                "area_id": first_area_id + len(records),
                "source_type": EncounterSourceType.HEADBUTT.value,
                **asdict(encounter),
                "location": {
                    "header_id": header.header_id,
                    "internal_name": header.internal_name,
                    "name": location_names[header.location_name_id],
                },
            }
        )
    return records


def _extract_safari_encounters(
    result: InspectionResult,
    engine: EncounterConcern,
    platform: Any,
    filesystem: Any,
    *,
    first_area_id: int,
) -> list[dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    archive_path = profile.layout.get("safari_encounters")
    if archive_path is None:
        return []
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    if len(archive.members) != len(engine.SAFARI_AREA_NAMES):
        raise InvalidRomError(
            f"Safari Zone archive has {len(archive.members)} members, expected "
            f"{len(engine.SAFARI_AREA_NAMES)}"
        )
    return [
        {
            "area_id": first_area_id + member.index,
            "source_type": EncounterSourceType.SAFARI_ZONE.value,
            **asdict(
                engine.parse_safari_encounter_record(
                    archive.read(member.index),
                    safari_area_id=member.index,
                    archive_path=archive_path,
                    species_count=engine.POKEMON_NAME_COUNT,
                )
            ),
        }
        for member in archive.members
    ]


def _extract_encounter_locations(
    engine: EncounterConcern,
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
        parameters = {name: profile.parameters[name] for name in required_parameters}
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing encounter location metadata: "
            f"{error.args[0]}"
        ) from error

    count = parameters["map_header_count"]
    table_offset = parameters["map_header_offset"]
    member = parameters["location_names_member"]
    arm9_data = read_code_binary(
        platform,
        result.image,
        compressed=COMPRESSED_CODE_BINARY in get_engine(profile.engine).capabilities,
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(layout["messages"]),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    headers, location_names = resolve_map_headers(
        engine,
        arm9_data,
        filesystem,
        messages,
        map_names_path=layout["map_names"],
        table_offset=table_offset,
        count=count,
        location_names_member=member,
    )

    locations: dict[int, list[EncounterLocation]] = {}
    null_encounter_id = profile.int_parameter(
        "null_encounter_id", engine.ARCHIVE_MEMBER_NONE
    )
    for header in headers:
        if header.encounter_id == null_encounter_id:
            continue
        if header.encounter_id >= encounter_count:
            raise InvalidRomError(
                f"Map header {header.header_id} references missing encounter "
                f"member {header.encounter_id}"
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
