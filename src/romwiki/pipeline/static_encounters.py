from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import STATIC_ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_static_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError(
            "A known game profile is required for static encounter extraction"
        )
    profile = result.match.profile
    try:
        scripts_path = profile.layout["scripts"]
        raw_entries = profile.parameters["static_pokemon"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing static encounter metadata: {error.args[0]}"
        ) from error
    egg_indices = frozenset(profile.parameters.get("static_pokemon_egg_indices", ()))

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).static_encounters
    filesystem = platform.filesystem_from_image(result.image)
    scripts = platform.archive_cls.from_bytes(filesystem.read(scripts_path))

    entries = [
        {
            "species": tuple(entry["species"]),
            "level": tuple(entry["level"]) if entry.get("level") is not None else None,
        }
        for entry in raw_entries
    ]
    encounters = engine.parse_static_encounters(
        scripts.read,
        entries,
        egg_indices=egg_indices,
        archive_path=scripts_path,
    )
    records = [encounter.to_dict() for encounter in encounters]
    return {
        "schema_version": STATIC_ENCOUNTERS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "static_encounters",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": scripts_path,
        },
        "records": records,
    }


def write_static_encounter_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
