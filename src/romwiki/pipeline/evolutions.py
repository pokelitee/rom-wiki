from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    parse_english_message_archive,
    parse_evolution_record,
)
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem


def extract_evolution_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for evolution extraction")
    profile = result.match.profile
    try:
        archive_path = profile.layout["evolutions"]
        message_archive_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define evolution item-name data"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    archive = NarcArchive.from_bytes(filesystem.read(archive_path))
    message_archive = NarcArchive.from_bytes(filesystem.read(message_archive_path))
    item_names = parse_english_message_archive(
        message_archive.read(item_names_member)
    )
    records = [
        parse_evolution_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "evolutions",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
            "item_names": {
                "archive": message_archive_path,
                "member": item_names_member,
            },
        },
        "item_names": list(item_names),
        "records": records,
    }


def write_evolution_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
