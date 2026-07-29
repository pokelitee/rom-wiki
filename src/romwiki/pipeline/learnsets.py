from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import POKEMON_LEARNSETS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


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
    adapter = get_engine(profile.engine)
    engine = adapter.learnsets
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(
        filesystem.read(archive_path),
        allow_incorrect_data_block_size=profile.parameters.get(
            "learnsets_allow_incorrect_data_block_size", False
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
    return {
        "schema_version": POKEMON_LEARNSETS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "dataset": "level_up_learnsets",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        "records": records,
    }


def write_learnset_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
