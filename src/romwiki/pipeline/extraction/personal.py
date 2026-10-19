from __future__ import annotations

from typing import Any

from romwiki.engines.concerns import PersonalConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.counts import leading_record_count, profile_count
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.reference_names import (
    extract_reference_descriptions,
    extract_reference_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import POKEMON_PERSONAL_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_personal_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError(
            "A known game profile is required for personal-data extraction"
        )
    profile = result.match.profile
    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).personal

    if platform.archive_cls is not None:
        records, source, reference_names, reference_descriptions = (
            _extract_personal_records_archive(profile, platform, engine, result)
        )
    elif platform.read_bytes is not None:
        records, source, reference_names = _extract_personal_records_flat(
            profile, platform, engine, result
        )
        reference_descriptions = _extract_ability_descriptions_flat(
            profile, platform, engine, result
        )
    else:
        raise ProfileError(
            f"Platform {profile.platform!r} supports neither archive nor flat reads"
        )

    envelope = dataset_envelope(
        schema_version=POKEMON_PERSONAL_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="pokemon_personal",
        source={"rom_sha256": result.image.hashes.sha256, **source},
        records=records,
    )
    envelope.update(reference_names)
    envelope.update(reference_descriptions)
    return envelope


def _extract_personal_records_archive(
    profile: Any, platform: Any, engine: PersonalConcern, result: InspectionResult
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        archive_path = profile.layout["personal"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a personal archive"
        ) from error

    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    reference_descriptions = extract_reference_descriptions(
        profile,
        filesystem,
        fields={"ability_descriptions", "pokemon_descriptions"},
    )
    members = archive.members[
        : leading_record_count(archive, engine.PERSONAL_RECORD_SIZE)
    ]
    parser_options = {}
    if profile.parameters.get("repair_invalid_secondary_egg_group", False):
        parser_options["repair_invalid_secondary_egg_group"] = True
    records = [
        engine.parse_personal_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
            **parser_options,
        ).to_dict()
        for member in members
    ]
    return records, {"archive": archive_path}, reference_names, reference_descriptions


def _extract_personal_records_flat(
    profile: Any, platform: Any, engine: PersonalConcern, result: InspectionResult
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    try:
        offset = profile.parameters["personal_offset"]
        count = profile.parameters["personal_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define personal_offset/personal_count"
        ) from error
    if not isinstance(offset, int) or not isinstance(count, int):
        raise ProfileError(
            f"Profile {profile.id} has an invalid personal_offset/personal_count"
        )

    record_size = engine.PERSONAL_RECORD_SIZE
    data = platform.read_bytes(result.image, offset, record_size * count)
    archive_path = f"offset:{offset:#x}"

    # Optional: a species-indexed TM/HM compatibility bitmap, separate from
    # the personal struct itself (unlike Generation IV/V, which embed it
    # inline) -- see `engines/gen3/frlg/machines.py`'s module comment. A
    # profile that doesn't declare this (or an engine with no such concept)
    # simply gets every record's `machine_ids`/`machine_masks` left at
    # `parse_personal_record`'s own empty default.
    tmhm_learnset_offset = profile.optional_int_parameter("tmhm_learnset_offset")
    tmhm_learnset_kwargs: dict[int, dict[str, Any]] = {}
    if tmhm_learnset_offset is not None:
        learnset_size = engine.MACHINE_LEARNSET_SIZE
        learnset_data = platform.read_bytes(
            result.image, tmhm_learnset_offset, learnset_size * count
        )
        tmhm_learnset_kwargs = {
            index: {
                "tmhm_learnset": learnset_data[
                    index * learnset_size : (index + 1) * learnset_size
                ]
            }
            for index in range(count)
        }

    records = [
        engine.parse_personal_record(
            data[index * record_size : (index + 1) * record_size],
            species_id=index,
            archive_path=archive_path,
            **tmhm_learnset_kwargs.get(index, {}),
        ).to_dict()
        for index in range(count)
    ]
    reference_names = _extract_names_flat(profile, platform, engine, result, count)
    return records, {"offset": offset}, reference_names


def _extract_names_flat(
    profile: Any,
    platform: Any,
    engine: PersonalConcern,
    result: InspectionResult,
    record_count: int,
) -> dict[str, Any]:
    # Each table is optional: without its offset, enrichment falls back to
    # PokéDB's names. Species names are one per personal record; a build with
    # a resized ability table sets ability_name_count.
    tables = {
        "ability_names": (
            "ability_name_offset",
            "ability_name_stride",
            profile_count(profile, "ability_name_count", engine.ABILITY_NAME_COUNT),
        ),
        "pokemon_names": ("pokemon_name_offset", "pokemon_name_stride", record_count),
    }
    result_names: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    for field, (offset_parameter, stride_parameter, count) in tables.items():
        offset = profile.optional_int_parameter(offset_parameter)
        if offset is None:
            continue
        stride = profile.int_parameter(stride_parameter)
        data = platform.read_bytes(result.image, offset, stride * count)
        result_names[field] = engine.decode_gen3_name_table(
            data, stride=stride, count=count
        )
        sources[field] = {"archive": f"offset:{offset:#x}", "member": 0}
    if sources:
        result_names["name_sources"] = sources
    return result_names


def _extract_ability_descriptions_flat(
    profile: Any, platform: Any, engine: PersonalConcern, result: InspectionResult
) -> dict[str, Any]:
    # Optional, like the name tables: a profile without
    # `ability_description_offset` skips ability descriptions.
    description_offset = profile.optional_int_parameter("ability_description_offset")
    if description_offset is None:
        return {}
    count = profile_count(profile, "ability_name_count", engine.ABILITY_NAME_COUNT)
    pointer_data = platform.read_bytes(result.image, description_offset, count * 4)
    descriptions = []
    for index in range(count):
        pointer = int.from_bytes(pointer_data[index * 4 : index * 4 + 4], "little")
        if pointer == 0:
            descriptions.append("")
            continue
        offset = engine.resolve_gba_pointer(pointer)
        # A generously-sized read (see `items.py`'s identical reasoning for
        # item descriptions) -- `decode_gen3_text` stops at the real 0xFF
        # terminator regardless of the exact string length.
        descriptions.append(
            engine.decode_gen3_text(platform.read_bytes(result.image, offset, 256))
        )
    return {
        "ability_descriptions": descriptions,
        "description_sources": {
            "ability_descriptions": {
                "archive": f"offset:{description_offset:#x}",
                "member": 0,
            }
        },
    }
