from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import (
    read_code_binary,
    resolve_map_headers,
)
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.semantics.encounter_identity import EncounterSourceType
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.encounters import EncounterLocation, EncounterMethod
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


def extract_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for encounter extraction")
    profile = result.match.profile
    encounter_format = get_engine(profile.engine).formats.encounters
    if encounter_format == "seasonal":
        return _extract_seasonal_encounter_dataset(result)
    if encounter_format == "method-table":
        return _extract_method_table_encounter_dataset(result)
    if encounter_format != "conditional":
        raise DataSourceError(f"Unsupported encounter format: {encounter_format!r}")
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
    engine: Any,
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
    map_header_count = profile.parameters["map_header_count"]
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
        read_code_binary(platform, result.image, engine),
        filesystem,
        messages,
        map_names_path=profile.layout["map_names"],
        table_offset=profile.parameters["map_header_offset"],
        count=map_header_count,
        location_names_member=profile.parameters["location_names_member"],
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
    engine: Any,
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


def _extract_method_table_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    # Generation III's wild-encounter mechanics (a flat per-map header table,
    # each of up to 4 methods reached through a pointer to a small
    # {rate, pointer-to-slots} struct -- a second level of pointer
    # indirection no other domain in this engine has needed) don't share
    # either Gen4's conditional shape or Gen5's seasonal shape, so this is a
    # standalone extraction path, the flat-offset analog of the archive
    # paths above.
    assert result.match is not None
    profile = result.match.profile
    try:
        offset = profile.parameters["encounter_offset"]
        count = profile.parameters["encounter_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define encounter_offset/encounter_count"
        ) from error
    if not isinstance(offset, int) or not isinstance(count, int):
        raise ProfileError(f"Profile {profile.id} has an invalid encounter parameter")

    platform = get_platform(profile.platform)
    if platform.read_bytes is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support flat reads")
    engine = get_engine(profile.engine).encounters
    header_size = engine.ENCOUNTER_HEADER_SIZE
    header_data = platform.read_bytes(result.image, offset, header_size * count)
    archive_path = f"offset:{offset:#x}"

    records = []
    for map_index in range(count):
        header = header_data[map_index * header_size : (map_index + 1) * header_size]
        map_group, map_num, pointers = engine.parse_header(header, map_index=map_index)
        methods: dict[str, Any] = {}
        for name in engine.ENCOUNTER_METHOD_NAMES:
            pointer = pointers[name]
            if pointer == 0:
                continue
            info_offset = engine.resolve_gba_pointer(pointer)
            info_data = platform.read_bytes(result.image, info_offset, 8)
            rate, slots_pointer = engine.parse_method_info(
                info_data, map_index=map_index, name=name
            )
            slot_count = {
                "land": engine.ENCOUNTER_LAND_SLOT_COUNT,
                "water": engine.ENCOUNTER_WATER_SLOT_COUNT,
                "rock_smash": engine.ENCOUNTER_ROCK_SMASH_SLOT_COUNT,
                "fishing": engine.ENCOUNTER_FISHING_SLOT_COUNT,
            }[name]
            slots_offset = engine.resolve_gba_pointer(slots_pointer)
            slots_data = platform.read_bytes(result.image, slots_offset, slot_count * 4)
            slots = engine.parse_method_slots(
                slots_data, map_index=map_index, name=name, count=slot_count
            )
            methods[name] = EncounterMethod(rate=rate, slots=slots)
        # No map-header/location system decoded for Generation III yet --
        # `parse_encounter_record` leaves `locations` at its dataclass
        # default (`()`) rather than guessing where a map is displayed,
        # same deferral already applied to trainer extraction.
        record = engine.parse_encounter_record(
            map_group,
            map_num,
            methods,
            map_index=map_index,
            archive_path=archive_path,
        )
        records.append(record.to_dict())

    envelope = dataset_envelope(
        schema_version=ENCOUNTERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="wild_encounters",
        source={"rom_sha256": result.image.hashes.sha256, "offset": offset},
        records=records,
    )
    return envelope


def _extract_seasonal_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    # This generation's wild-encounter mechanics (seven encounter methods per
    # area, up to four seasonal variants per map) don't share Gen4's shape
    # (walking/surf/rod/swarm/day/night/radar/dual-slot/Unown), so this is a
    # standalone extraction path rather than a variant of the one above.
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
        allow_trailing_data=profile.parameters.get(
            "encounters_allow_trailing_data", False
        ),
    )
    reference_names = extract_reference_names(profile, filesystem)
    areas = [
        area
        for member in archive.members
        for area in engine.parse_encounter_entry(
            archive.read(member.index),
            map_index=member.index,
            archive_path=archive_path,
        )
    ]
    wild_map_names, location_source = _extract_seasonal_wild_map_names(
        result, engine, platform, filesystem
    )
    records = [
        replace(
            area,
            area_id=index,
            location_names=tuple(wild_map_names.get(area.map_index, ())),
        ).to_dict()
        for index, area in enumerate(areas)
    ]
    records.extend(
        _extract_hidden_grottos(
            result,
            engine,
            platform,
            filesystem,
            first_area_id=len(records),
        )
    )
    records.extend(
        _extract_swarms(
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


def _extract_seasonal_wild_map_names(
    result: InspectionResult, engine: Any, platform: Any, filesystem: Any
) -> tuple[dict[int, list[str]], dict[str, Any]]:
    # Optional: a profile that doesn't declare this yet (or a future
    # generation reusing this path) simply gets unnamed encounter areas,
    # same as every other optional enrichment input in this codebase.
    assert result.match is not None
    profile = result.match.profile
    if (
        "map_headers" not in profile.layout
        or "map_names_member" not in profile.parameters
    ):
        return {}, {}
    map_headers_path = profile.layout["map_headers"]
    map_names_member = profile.parameters["map_names_member"]
    messages_path = profile.layout["messages"]
    map_headers = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    map_names = engine.parse_english_message_archive(messages.read(map_names_member))
    wild_map_names = engine.parse_wild_map_names(
        map_headers.read(0), map_names=tuple(map_names)
    )
    return wild_map_names, {
        "wild_map_names": {
            "map_headers_archive": map_headers_path,
            "map_names": {"archive": messages_path, "member": map_names_member},
        }
    }


def _extract_hidden_grottos(
    result: InspectionResult,
    engine: Any,
    platform: Any,
    filesystem: Any,
    *,
    first_area_id: int,
) -> list[dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    archive_path = profile.layout.get("hidden_grottos")
    if archive_path is None:
        return []
    version_group = profile.parameters.get("hidden_grotto_version_group")
    if not isinstance(version_group, int):
        raise ProfileError(
            f"Profile {profile.id} does not define a Hidden Grotto version group"
        )

    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    grotto_count = profile.parameters["hidden_grotto_record_count"]
    if len(archive.members) != grotto_count:
        raise InvalidRomError(
            f"Hidden Grotto archive has {len(archive.members)} members, expected "
            f"{grotto_count}"
        )
    map_headers_path = profile.layout["map_headers"]
    map_headers = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(profile.layout["messages"])
    )
    map_names = engine.parse_english_message_archive(
        messages.read(profile.parameters["map_names_member"])
    )
    headers = engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )
    overworlds = platform.archive_cls.from_bytes(
        filesystem.read(profile.layout["overworld_objects"]),
        allow_incorrect_data_block_size=profile.parameters.get(
            "field_archives_allow_incorrect_data_block_size", False
        ),
        allow_trailing_data=profile.parameters.get(
            "field_archives_allow_trailing_data", False
        ),
    )
    unused = frozenset(profile.parameters.get("overworld_objects_unused", ()))
    owners: dict[int, set[int]] = {}
    for header in headers:
        member = header.overworld_file_id
        if member is None or member >= len(overworlds.members) or member in unused:
            continue
        for furniture in engine.parse_overworld_furniture(overworlds.read(member)):
            grotto_id = engine.hidden_grotto_id_for_dispatch(
                furniture.script_used,
                dispatch_base=profile.parameters["hidden_grotto_dispatch_base"],
                grotto_count=grotto_count,
            )
            if grotto_id is not None:
                owners.setdefault(grotto_id, set()).add(header.header_id)
    expected = set(range(len(archive.members)))
    if set(owners) != expected:
        missing = sorted(expected - set(owners))
        extra = sorted(set(owners) - expected)
        raise InvalidRomError(
            f"Hidden Grotto dispatch mapping is incomplete (missing={missing}, "
            f"extra={extra})"
        )
    ambiguous = {key: sorted(value) for key, value in owners.items() if len(value) != 1}
    if ambiguous:
        raise InvalidRomError(
            f"Hidden Grotto dispatch mapping is ambiguous: {ambiguous}"
        )

    records = []
    valid_forms = frozenset(
        {*engine.ENCOUNTER_FORM_SLUGS, *engine.ENCOUNTER_COSMETIC_FORM_LABELS}
    )
    for grotto_id in range(len(archive.members)):
        grotto = engine.parse_hidden_grotto_record(
            archive.read(grotto_id),
            grotto_id=grotto_id,
            archive_path=archive_path,
            version_group=version_group,
            species_count=engine.POKEMON_NAME_COUNT,
            item_count=engine.ITEM_NAME_COUNT,
            valid_forms=valid_forms,
        )
        header_id = next(iter(owners[grotto_id]))
        header = headers[header_id]
        records.append(
            {
                "area_id": first_area_id + grotto_id,
                "source_type": EncounterSourceType.HIDDEN_GROTTO.value,
                **asdict(grotto),
                "location": {
                    "header_id": header.header_id,
                    "internal_name": header.internal_name,
                    "name": header.name,
                },
            }
        )
    return records


def _extract_swarms(
    result: InspectionResult,
    engine: Any,
    platform: Any,
    filesystem: Any,
    *,
    first_area_id: int,
) -> list[dict[str, Any]]:
    assert result.match is not None
    profile = result.match.profile
    required = ("swarm_overlay_id", "swarm_table_offset", "swarm_record_count")
    if not all(name in profile.parameters for name in required):
        return []
    overlay_id = profile.parameters["swarm_overlay_id"]
    table_offset = profile.parameters["swarm_table_offset"]
    record_count = profile.parameters["swarm_record_count"]
    overlay, overlay_data = platform.read_overlay_decompressed(result.image, overlay_id)
    table_size = record_count * engine.SWARM_RECORD_SIZE
    table_end = table_offset + table_size
    if not 0 <= table_offset <= table_end <= len(overlay_data):
        raise InvalidRomError(
            f"Swarm table 0x{table_offset:X}-0x{table_end:X} extends past "
            f"overlay {overlay_id}"
        )

    map_headers_path = profile.layout["map_headers"]
    map_headers = platform.archive_cls.from_bytes(
        filesystem.read(map_headers_path),
        allow_trailing_data=profile.parameters.get(
            "map_headers_allow_trailing_data", False
        ),
        allow_incorrect_data_block_size=profile.parameters.get(
            "map_headers_allow_incorrect_data_block_size", False
        ),
    )
    messages = platform.archive_cls.from_bytes(
        filesystem.read(profile.layout["messages"])
    )
    map_names = engine.parse_english_message_archive(
        messages.read(profile.parameters["map_names_member"])
    )
    headers = engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )
    swarms = engine.parse_swarm_table(
        overlay_data[table_offset:table_end],
        record_count=record_count,
        archive_path=f"overlay{overlay.id}",
        table_offset=table_offset,
        map_header_count=len(headers),
        species_count=engine.POKEMON_NAME_COUNT,
    )
    return [
        {
            "area_id": first_area_id + index,
            "source_type": EncounterSourceType.DAILY_SWARM.value,
            **asdict(swarm),
            "location": {
                "header_id": headers[swarm.header_id].header_id,
                "internal_name": headers[swarm.header_id].internal_name,
                "name": headers[swarm.header_id].name,
            },
        }
        for index, swarm in enumerate(swarms)
    ]


def _extract_encounter_locations(
    engine: Any,
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
    arm9_data = read_code_binary(platform, result.image, engine)
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
    null_encounter_id = profile.parameters.get(
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
