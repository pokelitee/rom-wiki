from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.counts import profile_count
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import STATIC_ENCOUNTERS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_static_encounter_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError(
            "A known game profile is required for static encounter extraction"
        )
    profile = result.match.profile
    try:
        scripts_path = profile.layout["scripts"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing static encounter metadata: {error.args[0]}"
        ) from error
    platform = get_platform(profile.platform)
    if platform.filesystem_from_image is None or platform.archive_cls is None:
        raise ProfileError(
            f"Platform {profile.platform!r} does not support archive-based extraction"
        )
    adapter = get_engine(profile.engine)
    engine = adapter.static_encounters
    filesystem = platform.filesystem_from_image(result.image)
    archive_options = {}
    if profile.parameters.get("field_archives_allow_incorrect_data_block_size", False):
        archive_options["allow_incorrect_data_block_size"] = True
    if profile.parameters.get("field_archives_allow_trailing_data", False):
        archive_options["allow_trailing_data"] = True
    scripts = platform.archive_cls.from_bytes(
        filesystem.read(scripts_path), **archive_options
    )

    if adapter.formats.static_encounters != "script-commands":
        raise ProfileError(
            f"Engine {profile.engine!r} does not support static encounter extraction"
        )
    encounters = engine.discover_static_encounters(
        scripts.read,
        member_count=len(scripts.members),
        archive_path=scripts_path,
        species_count=profile_count(
            profile, "pokemon_name_count", engine.POKEMON_NAME_COUNT
        ),
        item_count=profile_count(profile, "item_name_count", engine.ITEM_NAME_COUNT),
    )
    records = [encounter.to_dict() for encounter in encounters]
    return dataset_envelope(
        schema_version=STATIC_ENCOUNTERS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="static_encounters",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "archive": scripts_path,
        },
        records=records,
    )
