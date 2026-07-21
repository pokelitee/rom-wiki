from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import parse_level_up_learnset
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem


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

    filesystem = NintendoDSFileSystem.from_image(result.image)
    archive = NarcArchive.from_bytes(filesystem.read(archive_path))
    records = [
        parse_level_up_learnset(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return {
        "schema_version": 1,
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
