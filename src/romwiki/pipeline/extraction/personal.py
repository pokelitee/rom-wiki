from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
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
        reference_descriptions = {}
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
    profile: Any, platform: Any, engine: Any, result: InspectionResult
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
    # Bounded to the engine's declared record count rather than every archive
    # member: some engines' personal archives carry trailing members that
    # aren't personal records at all (e.g. Gen V's `a/0/1/6` has a non-record
    # table appended after the last species/forme entry).
    members = archive.members[: engine.PERSONAL_RECORD_COUNT]
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
    profile: Any, platform: Any, engine: Any, result: InspectionResult
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
    # `personal_count` in the profile is the table's real on-ROM size (used
    # to size the read); decoding is bounded to the engine's declared record
    # count, same reasoning as the archive path above.
    decoded_count = min(count, engine.PERSONAL_RECORD_COUNT)
    records = [
        engine.parse_personal_record(
            data[index * record_size : (index + 1) * record_size],
            species_id=index,
            archive_path=archive_path,
        ).to_dict()
        for index in range(decoded_count)
    ]
    reference_names = _extract_ability_names_flat(profile, platform, engine, result)
    return records, {"offset": offset}, reference_names


def _extract_ability_names_flat(
    profile: Any, platform: Any, engine: Any, result: InspectionResult
) -> dict[str, Any]:
    # Optional: an engine that hasn't wired up the "abilities" domain yet
    # (or a profile that doesn't declare these parameters) simply gets no
    # ability_names key, matching `resolve_ability_names`'s None-tolerant
    # fallback -- mirrors `moves.py`'s flat move-name decode, but this one
    # is optional rather than required since abilities is itself optional.
    name_offset = profile.parameters.get("ability_name_offset")
    name_stride = profile.parameters.get("ability_name_stride")
    name_count = profile.parameters.get("ability_name_count")
    if not all(
        isinstance(value, int) for value in (name_offset, name_stride, name_count)
    ):
        return {}
    name_data = platform.read_bytes(result.image, name_offset, name_stride * name_count)
    ability_names = engine.decode_gen3_text_table(
        name_data, stride=name_stride, count=name_count
    )
    return {
        "ability_names": ability_names,
        "name_sources": {
            "ability_names": {"archive": f"offset:{name_offset:#x}", "member": 0}
        },
    }
