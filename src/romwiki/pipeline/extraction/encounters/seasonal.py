from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from romwiki.engines.concerns import EncounterConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.counts import profile_count
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.pipeline.semantics.encounter_identity import EncounterSourceType
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError


def extract_seasonal_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
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
    result: InspectionResult, engine: EncounterConcern, platform: Any, filesystem: Any
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
    map_names_member = profile.int_parameter("map_names_member")
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
    engine: EncounterConcern,
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
    version_group = profile.optional_int_parameter("hidden_grotto_version_group")
    if version_group is None:
        raise ProfileError(
            f"Profile {profile.id} does not define a Hidden Grotto version group"
        )

    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    grotto_count = profile.int_parameter("hidden_grotto_record_count")
    if len(archive.members) != grotto_count:
        raise InvalidRomError(
            f"Hidden Grotto archive has {len(archive.members)} members, expected "
            f"{grotto_count}"
        )
    headers = _load_hidden_grotto_map_headers(profile, engine, platform, filesystem)
    owners = _resolve_hidden_grotto_owners(
        profile,
        engine,
        platform,
        filesystem,
        headers,
        grotto_count=grotto_count,
        member_count=len(archive.members),
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
            species_count=profile_count(
                profile, "pokemon_name_count", engine.POKEMON_NAME_COUNT
            ),
            item_count=profile_count(
                profile, "item_name_count", engine.ITEM_NAME_COUNT
            ),
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


def _load_hidden_grotto_map_headers(
    profile: Any, engine: EncounterConcern, platform: Any, filesystem: Any
) -> Any:
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
        messages.read(profile.int_parameter("map_names_member"))
    )
    return engine.parse_map_header_table(
        map_headers.read(0),
        map_names=tuple(map_names),
        archive_path=map_headers_path,
    )


def _resolve_hidden_grotto_owners(
    profile: Any,
    engine: EncounterConcern,
    platform: Any,
    filesystem: Any,
    headers: Any,
    *,
    grotto_count: int,
    member_count: int,
) -> dict[int, set[int]]:
    """Map each grotto to the one map header whose furniture dispatches to it."""
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
                dispatch_base=profile.int_parameter("hidden_grotto_dispatch_base"),
                grotto_count=grotto_count,
            )
            if grotto_id is not None:
                owners.setdefault(grotto_id, set()).add(header.header_id)
    expected = set(range(member_count))
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
    return owners


def _extract_swarms(
    result: InspectionResult,
    engine: EncounterConcern,
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
    overlay_id = profile.int_parameter("swarm_overlay_id")
    table_offset = profile.int_parameter("swarm_table_offset")
    record_count = profile.int_parameter("swarm_record_count")
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
        messages.read(profile.int_parameter("map_names_member"))
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
        species_count=profile_count(
            profile, "pokemon_name_count", engine.POKEMON_NAME_COUNT
        ),
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
