from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import POKEMON_EGG_MOVES_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def extract_egg_move_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for egg move extraction")
    egg_move_format = get_engine(result.match.profile.engine).formats.egg_moves
    if egg_move_format == "overlay-table":
        return _extract_from_overlay_table(result)
    if egg_move_format in {"archive-table", "species-archive"}:
        return _extract_from_archive(
            result, table_archive=egg_move_format == "archive-table"
        )
    raise ProfileError(
        f"Engine {result.match.profile.engine!r} does not support egg move extraction"
    )


def _extract_from_overlay_table(result: InspectionResult) -> dict[str, Any]:
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["egg_move_overlay_id"]
        table_offset = profile.parameters["egg_move_offset"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} does not define an egg move table"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).egg_moves
    overlay, data = platform.read_overlay(result.image, overlay_id)
    records = engine.parse_egg_move_table(data, table_offset=table_offset)
    return {
        "schema_version": POKEMON_EGG_MOVES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
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


def _extract_from_archive(
    result: InspectionResult, *, table_archive: bool
) -> dict[str, Any]:
    profile = result.match.profile
    archive_path = profile.layout["egg_moves"]
    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).egg_moves
    filesystem = platform.filesystem_from_image(result.image)
    archive = platform.archive_cls.from_bytes(filesystem.read(archive_path))
    if table_archive:
        if len(archive.members) != 1:
            raise ProfileError(
                f"Profile {profile.id} egg move table archive must contain one member"
            )
        records = engine.parse_egg_move_table(archive.read(0), table_offset=0)
        return {
            "schema_version": POKEMON_EGG_MOVES_RAW_SCHEMA_VERSION,
            "game": profile.id,
            "engine": profile.engine,
            "dataset": "egg_moves",
            "record_count": len(records),
            "move_reference_count": sum(len(record.move_ids) for record in records),
            "source": {
                "rom_sha256": result.image.hashes.sha256,
                "archive": archive_path,
                "member": 0,
            },
            "records": [record.to_dict() for record in records],
        }
    records = [
        engine.parse_egg_move_set(
            archive.read(member.index),
            species_id=member.index,
            archive_path=archive_path,
        ).to_dict()
        for member in archive.members
    ]
    return {
        "schema_version": POKEMON_EGG_MOVES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "egg_moves",
        "record_count": len(records),
        "move_reference_count": sum(len(record["move_ids"]) for record in records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": archive_path,
        },
        "records": records,
    }
