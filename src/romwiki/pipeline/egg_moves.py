from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import parse_egg_move_table
from romwiki.errors import ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds.overlays import read_arm9_overlay


def extract_egg_move_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for egg move extraction")
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["egg_move_overlay_id"]
        table_offset = profile.parameters["egg_move_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define an egg move table"
        ) from error

    overlay, data = read_arm9_overlay(result.image, overlay_id)
    records = parse_egg_move_table(data, table_offset=table_offset)
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "egg_moves",
        "record_count": len(records),
        "move_reference_count": sum(len(record.move_ids) for record in records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "overlay_file_id": overlay.file_id,
            "table_offset": table_offset,
        },
        "records": [record.to_dict() for record in records],
    }


def write_egg_move_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
