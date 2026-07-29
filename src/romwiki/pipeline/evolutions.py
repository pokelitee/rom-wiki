from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


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

    platform = get_platform(profile.platform)
    adapter = get_engine(profile.engine)
    engine = adapter.evolutions
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    message_archive = platform.archive_cls.from_bytes(
        filesystem.read(message_archive_path)
    )
    item_names = engine.parse_english_message_archive(
        message_archive.read(item_names_member)
    )
    records = [
        engine.parse_evolution_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members[: adapter.personal.PERSONAL_RECORD_COUNT]
    ]
    return {
        "schema_version": POKEMON_EVOLUTIONS_RAW_SCHEMA_VERSION,
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
