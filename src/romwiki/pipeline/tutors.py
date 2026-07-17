from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import (
    TUTOR_COMPATIBILITY_RECORD_SIZE,
    TUTOR_RECORD_SIZE,
    parse_tutor_compatibility_table,
    parse_tutor_move_table,
)
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds.overlays import read_arm9_overlay


def extract_tutor_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for tutor extraction")
    profile = result.match.profile
    required = (
        "tutor_overlay_id",
        "tutor_move_offset",
        "tutor_count",
        "tutor_compatibility_offset",
        "tutor_base_species_count",
        "tutor_form_member_start",
        "tutor_form_count",
        "tutor_location_names",
    )
    try:
        parameters = {name: profile.parameters[name] for name in required}
    except KeyError as error:
        raise ProfileError(f"Profile {profile.id} does not define tutor data") from error

    overlay, data = read_arm9_overlay(result.image, parameters["tutor_overlay_id"])
    move_size = parameters["tutor_count"] * TUTOR_RECORD_SIZE
    compatibility_count = (
        parameters["tutor_base_species_count"] + parameters["tutor_form_count"]
    )
    compatibility_size = compatibility_count * TUTOR_COMPATIBILITY_RECORD_SIZE
    move_data = _slice_overlay(data, parameters["tutor_move_offset"], move_size, "move")
    compatibility_data = _slice_overlay(
        data,
        parameters["tutor_compatibility_offset"],
        compatibility_size,
        "compatibility",
    )
    tutors = parse_tutor_move_table(move_data, tutor_count=parameters["tutor_count"])
    location_names = parameters["tutor_location_names"]
    if not isinstance(location_names, list) or any(
        not isinstance(name, str) or not name for name in location_names
    ):
        raise ProfileError("Tutor location names must be a list of nonempty strings")
    if any(tutor.location_id >= len(location_names) for tutor in tutors):
        raise InvalidRomError("Gen IV tutor references an unknown location ID")

    compatibility = parse_tutor_compatibility_table(
        compatibility_data,
        tutor_count=parameters["tutor_count"],
        base_species_count=parameters["tutor_base_species_count"],
        form_member_start=parameters["tutor_form_member_start"],
        form_count=parameters["tutor_form_count"],
    )
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "move_tutors",
        "record_count": len(tutors),
        "compatibility_record_count": len(compatibility),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "move_offset": parameters["tutor_move_offset"],
            "compatibility_offset": parameters["tutor_compatibility_offset"],
        },
        "location_names": location_names,
        "records": [tutor.to_dict() for tutor in tutors],
        "compatibility": [record.to_dict() for record in compatibility],
    }


def write_tutor_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(output_path)


def _slice_overlay(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or offset + size > len(data):
        raise InvalidRomError(f"Gen IV tutor {label} table is outside its overlay")
    return data[offset : offset + size]
