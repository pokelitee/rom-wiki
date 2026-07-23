from __future__ import annotations

from pathlib import Path
from typing import Any
from romwiki.schema.versions import MOVES_RAW_SCHEMA_VERSION

from romwiki.engines.registry import get_engine
from romwiki.platforms.registry import get_platform
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic
from romwiki.pipeline.identify import InspectionResult
from romwiki.pipeline.reference_names import extract_reference_names


def extract_move_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for move-data extraction")
    profile = result.match.profile
    try:
        archive_path = profile.layout["moves"]
    except KeyError as error:
        raise ProfileError(f"Profile {profile.id} does not define a move archive") from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).moves
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    records = [
        engine.parse_move_record(
            archive.read(member.index),
            move_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return {
        "schema_version": MOVES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "moves_raw",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        **reference_names,
        "records": records,
    }


def write_move_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
