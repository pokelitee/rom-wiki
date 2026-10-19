from __future__ import annotations

from typing import Any

from romwiki.engines.concerns import MoveConcern
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.reference_names import (
    extract_reference_descriptions,
    extract_reference_names,
)
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import MOVES_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_move_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for move-data extraction")
    profile = result.match.profile
    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).moves

    if platform.archive_cls is not None:
        records, source, reference_names, reference_descriptions = (
            _extract_move_records_archive(profile, platform, engine, result)
        )
    elif platform.read_bytes is not None:
        records, source, reference_names = _extract_move_records_flat(
            profile, platform, engine, result
        )
        reference_descriptions = {}
    else:
        raise ProfileError(
            f"Platform {profile.platform!r} supports neither archive nor flat reads"
        )

    envelope = dataset_envelope(
        schema_version=MOVES_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="moves",
        source={"rom_sha256": result.image.hashes.sha256, **source},
        records=records,
    )
    envelope.update(reference_names)
    envelope.update(reference_descriptions)
    return envelope


def _extract_move_records_archive(
    profile: Any, platform: Any, engine: MoveConcern, result: InspectionResult
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        archive_path = profile.layout["moves"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a move archive"
        ) from error

    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    reference_descriptions = extract_reference_descriptions(
        profile, filesystem, fields={"move_descriptions"}
    )
    records = [
        engine.parse_move_record(
            archive.read(member.index),
            move_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return records, {"archive": archive_path}, reference_names, reference_descriptions


def _extract_move_records_flat(
    profile: Any, platform: Any, engine: MoveConcern, result: InspectionResult
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    try:
        offset = profile.parameters["move_offset"]
        count = profile.parameters["move_count"]
        name_offset = profile.parameters["move_name_offset"]
        name_stride = profile.parameters["move_name_stride"]
        name_count = profile.parameters["move_name_count"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define move_offset/move_count/"
            "move_name_offset/move_name_stride/move_name_count"
        ) from error
    if not all(
        isinstance(value, int)
        for value in (offset, count, name_offset, name_stride, name_count)
    ):
        raise ProfileError(f"Profile {profile.id} has an invalid move parameter")

    record_size = engine.MOVE_RECORD_SIZE
    data = platform.read_bytes(result.image, offset, record_size * count)
    archive_path = f"offset:{offset:#x}"
    records = [
        engine.parse_move_record(
            data[index * record_size : (index + 1) * record_size],
            move_id=index,
            archive_path=archive_path,
        ).to_dict()
        for index in range(count)
    ]

    name_data = platform.read_bytes(result.image, name_offset, name_stride * name_count)
    move_names = engine.decode_gen3_name_table(
        name_data, stride=name_stride, count=name_count
    )
    reference_names = {
        "move_names": move_names,
        "name_sources": {
            "move_names": {"archive": f"offset:{name_offset:#x}", "member": 0}
        },
    }
    return records, {"offset": offset}, reference_names
