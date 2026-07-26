from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import MACHINES_RAW_SCHEMA_VERSION
from romwiki.util.byte_search import find_unique_pattern
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_machine_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for machine extraction")
    profile = result.match.profile
    if "machine_move_prefix" in profile.parameters:
        return _extract_from_arm9_prefix(result)
    return _extract_from_offset(result)


def _extract_from_offset(result: InspectionResult) -> dict[str, Any]:
    profile = result.match.profile
    try:
        # Unlike sibling extractors' ARM9-relative offsets (e.g. locations.py's
        # `map_header_offset`), `machine_move_offset` is an absolute ROM-image
        # file offset, bounds-checked against `result.image.size` below.
        offset = profile.parameters["machine_move_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a machine move table"
        ) from error
    engine = get_engine(profile.engine).machines
    machine_count = profile.parameters.get("machine_count", engine.MACHINE_COUNT)
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


def _extract_from_arm9_prefix(result: InspectionResult) -> dict[str, Any]:
    # Unlike Generation IV's fixed absolute file offset, this generation's
    # move table has no stable location: its ARM9 is BLZ-compressed, so the
    # table is found by byte-pattern search against the *decompressed*
    # binary (see platforms/nds/blz.py and Gen5RomHandler.java's
    # `getTMMoves`/tmDataPrefix).
    profile = result.match.profile
    prefix_hex = profile.parameters["machine_move_prefix"]
    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).machines
    arm9 = platform.read_decompressed_code_binary(result.image)
    prefix = bytes.fromhex(prefix_hex)
    offset = find_unique_pattern(
        arm9, prefix, label="the machine move table in ARM9"
    ) + len(prefix)
    size = engine.MACHINE_COUNT * 2
    if offset + size > len(arm9):
        raise InvalidRomError(
            "Gen V machine move table is outside the decompressed ARM9"
        )
    data = arm9[offset : offset + size]
    records = [machine.to_dict() for machine in engine.parse_machine_move_table(data)]
    return {
        "schema_version": MACHINES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "dataset": "machines",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "arm9_prefix": prefix_hex,
            "arm9_offset": offset,
            "size": size,
        },
        "records": records,
    }


def write_machine_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
