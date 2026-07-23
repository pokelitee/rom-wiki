from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import PICKUP_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_pickup_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for pickup extraction")
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["pickup_overlay_id"]
        common_offset = profile.parameters["pickup_common_items_offset"]
        rare_offset = profile.parameters["pickup_rare_items_offset"]
        common_rate_offset = profile.parameters["pickup_common_rate_offset"]
        honey_rate_offset = profile.parameters["pickup_honey_gather_rate_offset"]
        common_count = profile.parameters["pickup_common_item_count"]
        rare_count = profile.parameters["pickup_rare_item_count"]
        rate_count = profile.parameters["pickup_common_rate_count"]
        honey_rate_count = profile.parameters["pickup_honey_gather_rate_count"]
        item_names_member = profile.parameters["item_names_member"]
        messages_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing pickup metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).items
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    _, overlay_data = platform.read_overlay(result.image, overlay_id)
    tables = engine.parse_pickup_tables(
        overlay_data,
        common_offset=common_offset,
        rare_offset=rare_offset,
        common_rate_offset=common_rate_offset,
        honey_rate_offset=honey_rate_offset,
        common_count=common_count,
        rare_count=rare_count,
        rate_count=rate_count,
        honey_rate_count=honey_rate_count,
        item_count=len(item_names),
    )
    return {
        "schema_version": PICKUP_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "dataset": "pickup",
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay_id,
        },
        "tables": {
            "common_items": [
                {"item_id": item_id, "name": item_names[item_id]}
                for item_id in tables.common_item_ids
            ],
            "rare_items": [
                {"item_id": item_id, "name": item_names[item_id]}
                for item_id in tables.rare_item_ids
            ],
            "common_rate": tables.common_rate,
            "honey_gather_rate": tables.honey_gather_rate,
        },
    }


def write_pickup_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
