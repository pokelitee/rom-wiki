from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import parse_personal_record
from romwiki.errors import ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem


def extract_personal_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for personal-data extraction")
    profile = result.match.profile
    try:
        archive_path = profile.layout["personal"]
    except KeyError as error:
        raise ProfileError(f"Profile {profile.id} does not define a personal archive") from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    archive = NarcArchive.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    records = [
        parse_personal_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "pokemon_personal",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        **reference_names,
        "records": records,
    }


def write_personal_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
