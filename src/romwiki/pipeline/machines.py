from __future__ import annotations

from pathlib import Path
from typing import Any
from romwiki.schema.versions import MACHINES_RAW_SCHEMA_VERSION

from romwiki.engines.registry import get_engine
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic
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
    engine = get_engine(profile.engine).machines
    machine_count = profile.parameters.get("machine_count", engine.GEN4_MACHINE_COUNT)
    tm_count = profile.parameters.get("tm_count", engine.GEN4_TM_COUNT)

    size = machine_count * 2
    if offset < 0 or offset + size > result.image.size:
        raise InvalidRomError("Gen IV machine move table is outside the ROM image")
    with result.image.path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(size)
    records = [
        machine.to_dict()
        for machine in engine.parse_machine_move_table(
            data,
            machine_count=machine_count,
            tm_count=tm_count,
        )
    ]
    return {
        "schema_version": MACHINES_RAW_SCHEMA_VERSION,
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
    write_json_atomic(output_path, dataset)
