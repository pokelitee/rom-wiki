from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    MAP_HEADER_SIZE,
    Gen4WarpEvent,
    PlatinumMapHeader,
    parse_english_message_archive,
    parse_map_matrix,
    parse_platinum_map_headers,
    parse_warp_events,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.trainers import extract_trainer_dataset
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem
from romwiki.schema import (
    Gen4Location,
    LocationConnection,
    LocationTrainerReference,
    LocationWarp,
)


def extract_location_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for location extraction")
    profile = result.match.profile
    try:
        events_path = profile.layout["events"]
        matrices_path = profile.layout["map_matrices"]
        map_names_path = profile.layout["map_names"]
        messages_path = profile.layout["messages"]
        count = profile.parameters["map_header_count"]
        table_offset = profile.parameters["map_header_offset"]
        location_names_member = profile.parameters["location_names_member"]
        null_event_id = profile.parameters["null_event_id"]
        null_encounter_id = profile.parameters["null_encounter_id"]
        dynamic_warp_header_id = profile.parameters["dynamic_warp_header_id"]
        dynamic_warp_id = profile.parameters["dynamic_warp_id"]
        matrix_void_header_ids = frozenset(
            profile.parameters["matrix_void_header_ids"]
        )
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing location metadata: {error.args[0]}"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    with result.image.path.open("rb") as stream:
        stream.seek(result.image.header.arm9_offset + table_offset)
        header_data = stream.read(count * MAP_HEADER_SIZE)
    headers = parse_platinum_map_headers(
        header_data, filesystem.read(map_names_path), count=count
    )
    messages = NarcArchive.from_bytes(filesystem.read(messages_path))
    location_names = parse_english_message_archive(
        messages.read(location_names_member)
    )
    events = NarcArchive.from_bytes(filesystem.read(events_path))
    matrices = NarcArchive.from_bytes(filesystem.read(matrices_path))

    warps_by_event: dict[int, tuple[Gen4WarpEvent, ...]] = {}
    raw_warps_by_header: dict[int, tuple[Gen4WarpEvent, ...]] = {}
    for header in headers:
        if header.location_name_id >= len(location_names):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing location name "
                f"{header.location_name_id}"
            )
        if header.event_file_id == null_event_id:
            raw_warps_by_header[header.header_id] = ()
            continue
        if header.event_file_id >= len(events.members):
            raise InvalidRomError(
                f"Map header {header.header_id} references missing event file "
                f"{header.event_file_id}"
            )
        if header.event_file_id not in warps_by_event:
            warps_by_event[header.event_file_id] = parse_warp_events(
                events.read(header.event_file_id), event_file_id=header.event_file_id
            )
        raw_warps_by_header[header.header_id] = warps_by_event[header.event_file_id]

    connections = _extract_matrix_connections(
        headers, matrices, location_names, matrix_void_header_ids
    )
    trainers = _extract_trainer_references(result)
    records = []
    for header in headers:
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
                        destination_internal_name=None,
                        destination_warp_exists=None,
                        dynamic=True,
                    )
                )
                continue
            if not 0 <= warp.destination_header_id < len(headers):
                raise InvalidRomError(
                    f"Map header {header.header_id} warp {warp.index} references "
                    f"missing header {warp.destination_header_id}"
                )
            destination = headers[warp.destination_header_id]
            destination_warps = raw_warps_by_header[destination.header_id]
            warps.append(
                LocationWarp(
                    index=warp.index,
                    x=warp.x,
                    z=warp.z,
                    destination_header_id=destination.header_id,
                    destination_warp_id=warp.destination_warp_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_internal_name=destination.internal_name,
                    destination_warp_exists=(
                        warp.destination_warp_id < len(destination_warps)
                    ),
                    dynamic=False,
                )
            )
        records.append(
            Gen4Location(
                header_id=header.header_id,
                internal_name=header.internal_name,
                location_name_id=header.location_name_id,
                name=location_names[header.location_name_id],
                matrix_id=header.matrix_id,
                event_file_id=(
                    None
                    if header.event_file_id == null_event_id
                    else header.event_file_id
                ),
                encounter_id=(
                    None
                    if header.encounter_id == null_encounter_id
                    else header.encounter_id
                ),
                warps=tuple(warps),
                connections=tuple(connections.get(header.header_id, ())),
                trainers=tuple(trainers.get(header.header_id, ())),
            ).to_dict()
        )
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "locations",
        "record_count": len(records),
        "warp_count": sum(len(record["warps"]) for record in records),
        "dynamic_warp_count": sum(
            warp["dynamic"] for record in records for warp in record["warps"]
        ),
        "missing_destination_warp_count": sum(
            warp["destination_warp_exists"] is False
            for record in records
            for warp in record["warps"]
        ),
        "connection_count": sum(len(record["connections"]) for record in records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "events_archive": events_path,
            "map_matrices_archive": matrices_path,
            "map_headers": {"arm9_offset": table_offset, "count": count},
            "internal_names": map_names_path,
            "location_names": {
                "archive": messages_path,
                "member": location_names_member,
            },
        },
        "records": records,
    }


def _extract_matrix_connections(
    headers: tuple[PlatinumMapHeader, ...],
    matrices: NarcArchive,
    location_names: tuple[str, ...],
    void_header_ids: frozenset[int],
) -> dict[int, list[LocationConnection]]:
    directions: dict[int, dict[int, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for matrix_id in sorted({header.matrix_id for header in headers}):
        if matrix_id >= len(matrices.members):
            raise InvalidRomError(f"Map header references missing matrix {matrix_id}")
        matrix = parse_map_matrix(matrices.read(matrix_id), matrix_id=matrix_id)
        if matrix.header_ids is None:
            continue
        for index, source in enumerate(matrix.header_ids):
            if source in void_header_ids:
                continue
            if source >= len(headers):
                raise InvalidRomError(
                    f"Map matrix {matrix_id} references missing header {source}"
                )
            x = index % matrix.width
            z = index // matrix.width
            for offset, forward, reverse in (
                (1, "east", "west"),
                (matrix.width, "south", "north"),
            ):
                if (forward == "east" and x + 1 >= matrix.width) or (
                    forward == "south" and z + 1 >= matrix.height
                ):
                    continue
                destination = matrix.header_ids[index + offset]
                if destination == source or destination in void_header_ids:
                    continue
                if destination >= len(headers):
                    raise InvalidRomError(
                        f"Map matrix {matrix_id} references missing header "
                        f"{destination}"
                    )
                directions[source][destination].add(forward)
                directions[destination][source].add(reverse)

    result = {}
    direction_order = {"north": 0, "east": 1, "south": 2, "west": 3}
    for source, destinations in directions.items():
        result[source] = []
        for destination_id, values in sorted(destinations.items()):
            destination = headers[destination_id]
            result[source].append(
                LocationConnection(
                    destination_header_id=destination_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_internal_name=destination.internal_name,
                    directions=tuple(sorted(values, key=direction_order.__getitem__)),
                )
            )
    return result


def _extract_trainer_references(
    result: InspectionResult,
) -> dict[int, list[LocationTrainerReference]]:
    references: dict[int, list[LocationTrainerReference]] = defaultdict(list)
    seen: set[tuple[int, int, str]] = set()
    for trainer in extract_trainer_dataset(result)["records"]:
        for source, locations in (
            ("overworld-object", trainer["locations"]),
            ("map-script", trainer["script_references"]),
        ):
            for location in locations:
                key = (location["header_id"], trainer["trainer_id"], source)
                if key in seen:
                    continue
                seen.add(key)
                references[location["header_id"]].append(
                    LocationTrainerReference(
                        trainer_id=trainer["trainer_id"],
                        name=trainer["name"],
                        class_name=trainer["class_name"],
                        source=source,
                    )
                )
    for values in references.values():
        values.sort(key=lambda item: (item.class_name, item.name, item.trainer_id))
    return references


def write_location_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output_path)
