from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    GEN4_MACHINE_COUNT,
    GEN4_TM_COUNT,
    parse_machine_move_table,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult


def extract_machine_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for machine extraction")
    profile = result.match.profile
    try:
        offset = profile.parameters["machine_move_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a machine move table"
        ) from error
    machine_count = profile.parameters.get("machine_count", GEN4_MACHINE_COUNT)
    tm_count = profile.parameters.get("tm_count", GEN4_TM_COUNT)

    size = machine_count * 2
    if offset < 0 or offset + size > result.image.size:
        raise InvalidRomError("Gen IV machine move table is outside the ROM image")
    with result.image.path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(size)
    records = [
        machine.to_dict()
        for machine in parse_machine_move_table(
            data,
            machine_count=machine_count,
            tm_count=tm_count,
        )
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "machines",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "offset": offset,
            "size": size,
        },
        "records": records,
    }


def write_machine_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
