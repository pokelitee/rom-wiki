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
from romwiki.schema.versions import MOVES_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_move_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for move-data extraction")
    profile = result.match.profile
    try:
        archive_path = profile.layout["moves"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a move archive"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).moves
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
    envelope = dataset_envelope(
        schema_version=MOVES_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="moves",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        records=records,
    )
    envelope.update(reference_names)
    envelope.update(reference_descriptions)
    return envelope
