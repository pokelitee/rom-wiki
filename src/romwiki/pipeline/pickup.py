from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import PICKUP_RAW_SCHEMA_VERSION
from romwiki.util.byte_search import find_unique_pattern
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_pickup_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for pickup extraction")
    profile = result.match.profile
    if "pickup_table_locator" in profile.parameters:
        return _extract_gen5(result)
    return _extract_gen4(result)


def _extract_gen4(result: InspectionResult) -> dict[str, Any]:
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
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
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
        "engine": profile.engine,
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


def _extract_gen5(result: InspectionResult) -> dict[str, Any]:
    # Unlike Generation IV's fixed absolute overlay offsets, this
    # generation's pickup item table has no stable location: it's found by
    # byte-pattern search (see gen5_bw/pickup.py's own module comment), the
    # same technique used for the TM/HM move table.
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["pickup_overlay_id"]
        locator_hex = profile.parameters["pickup_table_locator"]
        item_names_member = profile.parameters["item_names_member"]
        messages_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing pickup metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    items_engine = get_engine(profile.engine).items
    pickup_engine = get_engine(profile.engine).pickup
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = items_engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    _, overlay_data = platform.read_overlay_decompressed(result.image, overlay_id)
    locator = bytes.fromhex(locator_hex)
    table_offset = find_unique_pattern(
        overlay_data, locator, label="the pickup item table"
    )
    table = pickup_engine.parse_pickup_table(
        overlay_data, table_offset=table_offset, archive_path=f"overlay{overlay_id}"
    )
    level_ranges = [
        {
            "minimum_level": level_range * pickup_engine.PICKUP_LEVEL_RANGE_SIZE + 1,
            "maximum_level": (level_range + 1) * pickup_engine.PICKUP_LEVEL_RANGE_SIZE,
            "slots": [
                {"item_id": item_id, "name": item_names[item_id], "chance": chance}
                for item_id, chance in zip(
                    pickup_engine.pickup_level_range_item_ids(
                        table.item_ids, level_range
                    ),
                    pickup_engine.PICKUP_SLOT_CHANCES,
                    strict=True,
                )
            ],
        }
        for level_range in range(pickup_engine.PICKUP_LEVEL_RANGE_COUNT)
    ]
    return {
        "schema_version": PICKUP_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "pickup",
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay_id,
            "table_offset": table_offset,
        },
        "level_ranges": level_ranges,
    }


def write_pickup_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
