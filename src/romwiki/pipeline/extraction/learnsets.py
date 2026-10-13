from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import POKEMON_LEARNSETS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_learnset_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for learnset extraction")
    profile = result.match.profile
    try:
        archive_path = profile.layout["learnsets"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a level-up learnset archive"
        ) from error

    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    adapter = get_engine(profile.engine)
    engine = adapter.learnsets
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(
        filesystem.read(archive_path),
        allow_truncated=profile.parameters.get("learnsets_allow_truncated", False),
        allow_incorrect_data_block_size=profile.parameters.get(
            "learnsets_allow_incorrect_data_block_size", False
        ),
        allow_trailing_data=profile.parameters.get(
            "learnsets_allow_trailing_data", False
        ),
    )
    records = [
        engine.parse_level_up_learnset(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members[: adapter.personal.PERSONAL_RECORD_COUNT]
    ]
    return dataset_envelope(
        schema_version=POKEMON_LEARNSETS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="level_up_learnsets",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        records=records,
    )
