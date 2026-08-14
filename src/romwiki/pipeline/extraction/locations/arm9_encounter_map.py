from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.helpers import (
    extract_event_map_connections,
    extract_event_map_items,
    extract_trainer_references,
)
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.semantics.location_sections import (
    resolve_location_section,
    validate_location_sections,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema import (
    EncounterMapLocation,
    LocationItem,
    LocationWarp,
    RecordProvenance,
)
from romwiki.schema.versions import LOCATIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_arm9_encounter_map_location_dataset(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
    item_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        encounters_path = profile.layout["encounters"]
        events_path = profile.layout["events"]
        matrices_path = profile.layout["map_matrices"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).locations
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    encounters = platform.archive_cls.from_bytes(
        filesystem.read(encounters_path),
        allow_truncated=profile.parameters.get("encounters_allow_truncated", False),
    )
    event_options = {}
    if profile.parameters.get("events_allow_incorrect_data_block_size", False):
        event_options["allow_incorrect_data_block_size"] = True
    events = platform.archive_cls.from_bytes(
        filesystem.read(events_path), **event_options
    )
    matrices = platform.archive_cls.from_bytes(filesystem.read(matrices_path))
    arm9_data = read_code_binary(platform, result.image, engine)
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
    validate_location_sections(
        profile,
        ((header.header_id, header.internal_name) for header in headers),
    )
    null_encounter_id = profile.parameters.get(
        "null_encounter_id", engine.ENCOUNTER_MEMBER_NONE
    )
    null_event_id = profile.parameters.get("null_event_id", engine.ARCHIVE_MEMBER_NONE)
    dynamic_warp_header_id = profile.parameters.get(
        "dynamic_warp_header_id", engine.DYNAMIC_WARP_HEADER_ID
    )
    dynamic_warp_id = profile.parameters.get("dynamic_warp_id", engine.DYNAMIC_WARP_ID)
    matrix_void_header_ids = frozenset(
        profile.parameters.get("matrix_void_header_ids", engine.MATRIX_VOID_HEADER_IDS)
    )
    item_names = tuple(
        record["name"] for record in (item_dataset or {}).get("records", ())
    ) or engine.parse_english_message_archive(messages.read(item_names_member))
    parsed_events: dict[int, Any] = {}
    items_by_event: dict[int, tuple[LocationItem, ...]] = {}
    raw_warps_by_header: dict[int, tuple[Any, ...]] = {}
    for header in headers:
        if header.event_file_id == null_event_id:
            raw_warps_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in parsed_events:
            parsed = engine.parse_map_events(
                events.read(header.event_file_id), event_file_id=header.event_file_id
            )
            parsed_events[header.event_file_id] = parsed
            items_by_event[header.event_file_id] = (
                extract_event_map_items(engine, parsed, item_names)
                if item_names
                else ()
            )
        raw_warps_by_header[header.header_id] = parsed_events[
            header.event_file_id
        ].warps
    connections = extract_event_map_connections(
        engine, headers, matrices, location_names, matrix_void_header_ids
    )
    trainers = extract_trainer_references(result, trainer_dataset)
    records = []
    for header in headers:
        section_name, section_name_source = resolve_location_section(
            profile,
            header_id=header.header_id,
            internal_name=header.internal_name,
        )
        encounter_id = header.encounter_id
        encounter_map_index = (
            None if encounter_id == null_encounter_id else encounter_id
        )
        if encounter_map_index is not None and encounter_map_index >= len(
            encounters.members
        ):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing encounter "
                f"member {encounter_map_index}"
            )
        warps = []
        for warp in raw_warps_by_header[header.header_id]:
            dynamic = (
                warp.destination_header_id == dynamic_warp_header_id
                and warp.destination_warp_id == dynamic_warp_id
            )
            if dynamic:
                warps.append(
                    LocationWarp(
                        index=warp.index,
                        x=warp.x,
                        z=warp.z,
                        destination_header_id=None,
                        destination_warp_id=None,
                        destination_name=None,
                        destination_section_name=None,
                        destination_internal_name=None,
                        destination_warp_exists=None,
                        dynamic=True,
                    )
                )
                continue
            if warp.destination_header_id >= len(headers):
                raise InvalidRomError(
                    f"Map header {header.header_id} warp {warp.index} references "
                    f"missing header {warp.destination_header_id}"
                )
            destination = headers[warp.destination_header_id]
            destination_section_name, _ = resolve_location_section(
                profile,
                header_id=destination.header_id,
                internal_name=destination.internal_name,
            )
            warps.append(
                LocationWarp(
                    index=warp.index,
                    x=warp.x,
                    z=warp.z,
                    destination_header_id=destination.header_id,
                    destination_warp_id=warp.destination_warp_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_section_name=destination_section_name,
                    destination_internal_name=destination.internal_name,
                    destination_warp_exists=(
                        warp.destination_warp_id
                        < len(raw_warps_by_header[destination.header_id])
                    ),
                    dynamic=False,
                )
            )
        records.append(
            EncounterMapLocation(
                header_id=header.header_id,
                name=location_names[header.location_name_id],
                encounter_map_index=encounter_map_index,
                matrix_id=header.matrix_id,
                internal_name=header.internal_name,
                section_name=section_name,
                section_name_source=section_name_source,
                trainers=tuple(trainers.get(header.header_id, ())),
                warps=tuple(warps),
                connections=tuple(connections.get(header.header_id, ())),
                items=(
                    ()
                    if header.event_file_id == null_event_id
                    else items_by_event[header.event_file_id]
                ),
                provenance=RecordProvenance(
                    source="rom", archive="arm9", member=header.header_id
                ),
            ).to_dict()
        )
    return {
        "schema_version": LOCATIONS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "locations",
        "record_count": len(records),
        "warp_count": sum(len(record["warps"]) for record in records),
        "connection_count": sum(len(record["connections"]) for record in records),
        "visible_item_count": sum(
            item["kind"] == "visible" for record in records for item in record["items"]
        ),
        "hidden_item_count": sum(
            item["kind"] == "hidden" for record in records for item in record["items"]
        ),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "events_archive": events_path,
            "map_matrices_archive": matrices_path,
            "location_names": {
                "archive": messages_path,
                "member": location_names_member,
            },
            "item_names": {
                "archive": messages_path,
                "member": item_names_member,
            },
        },
        "records": records,
    }
