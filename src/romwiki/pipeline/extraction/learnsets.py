from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.counts import personal_archive_count
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import POKEMON_LEARNSETS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_learnset_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for learnset extraction")
    profile = result.match.profile
    platform = get_platform(profile.platform)
    if platform.archive_cls is None and platform.read_bytes is not None:
        return _extract_learnset_dataset_flat(result, profile, platform)
    try:
        archive_path = profile.layout["learnsets"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a level-up learnset archive"
        ) from error

    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    engine = get_engine(profile.engine).learnsets
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
        for member in archive.members[
            : personal_archive_count(profile, platform, filesystem)
        ]
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


def _extract_learnset_dataset_flat(
    result: InspectionResult, profile: Any, platform: Any
) -> dict[str, Any]:
    """Read a pointer table with one learnset pointer per personal record."""
    offset = profile.int_parameter("learnset_offset")
    count = profile.int_parameter("personal_count")
    engine = get_engine(profile.engine).learnsets
    pointer_size = engine.LEARNSET_POINTER_SIZE
    pointers = platform.read_bytes(result.image, offset, pointer_size * count)
    archive_path = f"offset:{offset:#x}"
    records = []
    for species_id in range(count):
        pointer = int.from_bytes(
            pointers[species_id * pointer_size : (species_id + 1) * pointer_size],
            "little",
        )
        records.append(
            engine.parse_level_up_learnset(
                platform.read_bytes(
                    result.image,
                    engine.resolve_gba_pointer(pointer),
                    engine.LEARNSET_READ_SIZE,
                ),
                species_id=species_id,
                archive_path=archive_path,
            ).to_dict()
        )
    return dataset_envelope(
        schema_version=POKEMON_LEARNSETS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="level_up_learnsets",
        source={"rom_sha256": result.image.hashes.sha256, "offset": offset},
        records=records,
    )
