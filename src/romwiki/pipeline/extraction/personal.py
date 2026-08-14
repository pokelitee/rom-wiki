from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.reference_names import extract_reference_names
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import POKEMON_PERSONAL_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_personal_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError(
            "A known game profile is required for personal-data extraction"
        )
    profile = result.match.profile
    try:
        archive_path = profile.layout["personal"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define a personal archive"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).personal
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    reference_names = extract_reference_names(profile, filesystem)
    # Bounded to the engine's declared record count rather than every archive
    # member: some engines' personal archives carry trailing members that
    # aren't personal records at all (e.g. Gen V's `a/0/1/6` has a non-record
    # table appended after the last species/forme entry).
    members = archive.members[: engine.PERSONAL_RECORD_COUNT]
    parser_options = {}
    if profile.parameters.get("repair_invalid_secondary_egg_group", False):
        parser_options["repair_invalid_secondary_egg_group"] = True
    records = [
        engine.parse_personal_record(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
            **parser_options,
        ).to_dict()
        for member in members
    ]
    return {
        "schema_version": POKEMON_PERSONAL_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "pokemon_personal",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        **reference_names,
        "records": records,
    }
