from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import PICKUP_RAW_SCHEMA_VERSION
from romwiki.util.byte_search import find_unique_pattern
from romwiki.util.errors import DataSourceError, ProfileError


def extract_pickup_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for pickup extraction")
    profile = result.match.profile
    pickup_format = get_engine(profile.engine).formats.pickup
    if pickup_format == "locator-tables":
        return _extract_locator_tables(result)
    if pickup_format == "sliding-table":
        return _extract_sliding_table(result)
    if pickup_format == "split-table":
        return _extract_split_table(result)
    raise DataSourceError(
        f"Engine {profile.engine!r} does not provide pickup extraction"
    )


def _extract_split_table(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["pickup_overlay_id"]
        common_offset = profile.parameters["pickup_common_items_offset"]
        rare_offset = profile.parameters["pickup_rare_items_offset"]
        common_rate_offset = profile.parameters["pickup_common_rate_offset"]
        honey_rate_offset = profile.parameters["pickup_honey_gather_rate_offset"]
        item_names_member = profile.parameters["item_names_member"]
        messages_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing pickup metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).pickup
    common_count = profile.parameters.get(
        "pickup_common_item_count", engine.PICKUP_COMMON_ITEM_COUNT
    )
    rare_count = profile.parameters.get(
        "pickup_rare_item_count", engine.PICKUP_RARE_ITEM_COUNT
    )
    rate_count = profile.parameters.get(
        "pickup_common_rate_count", engine.PICKUP_COMMON_RATE_COUNT
    )
    honey_rate_count = profile.parameters.get(
        "pickup_honey_gather_rate_count", engine.PICKUP_HONEY_GATHER_RATE_COUNT
    )
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    if platform.read_overlay is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
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
        "record_count": 1,
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


def _extract_locator_tables(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["pickup_overlay_id"]
        item_names_member = profile.parameters["item_names_member"]
        messages_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing pickup metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).pickup
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    if platform.read_overlay_decompressed is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    overlay, overlay_data = platform.read_overlay_decompressed(result.image, overlay_id)
    common_offset = find_unique_pattern(
        overlay_data,
        bytes.fromhex(engine.PICKUP_COMMON_TABLE_LOCATOR),
        label="the common Pickup item table",
    )
    rare_offset = find_unique_pattern(
        overlay_data,
        bytes.fromhex(engine.PICKUP_RARE_TABLE_LOCATOR),
        label="the rare Pickup item table",
    )
    common_items = engine.parse_pickup_item_table(
        overlay_data,
        offset=common_offset,
        count=engine.PICKUP_COMMON_ITEM_COUNT,
        item_count=len(item_names),
    )
    rare_items = engine.parse_pickup_item_table(
        overlay_data,
        offset=rare_offset,
        count=engine.PICKUP_RARE_ITEM_COUNT,
        item_count=len(item_names),
    )
    level_ranges = []
    for level_range in range(engine.PICKUP_LEVEL_RANGE_COUNT):
        item_ids = engine.pickup_level_range_item_ids(
            common_items, rare_items, level_range
        )
        level_ranges.append(
            {
                "minimum_level": level_range * engine.PICKUP_LEVEL_RANGE_SIZE + 1,
                "maximum_level": (level_range + 1) * engine.PICKUP_LEVEL_RANGE_SIZE,
                "slots": [
                    {
                        "item_id": item_id,
                        "name": item_names[item_id],
                        "chance": chance,
                    }
                    for item_id, chance in zip(
                        item_ids, engine.PICKUP_SLOT_CHANCES, strict=True
                    )
                ],
            }
        )
    return {
        "schema_version": PICKUP_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "pickup",
        "record_count": 1,
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay.id,
            "file_id": overlay.file_id,
            "common_offset": common_offset,
            "rare_offset": rare_offset,
        },
        "level_ranges": level_ranges,
    }


def _extract_sliding_table(result: InspectionResult) -> dict[str, Any]:
    # Unlike Generation IV's fixed absolute overlay offsets, this
    # generation's pickup item table has no stable location: it's found by
    # byte-pattern search (see gen5/bw/pickup.py's own module comment), the
    # same technique used for the TM/HM move table.
    assert result.match is not None
    profile = result.match.profile
    try:
        overlay_id = profile.parameters["pickup_overlay_id"]
        item_names_member = profile.parameters["item_names_member"]
        messages_path = profile.layout["messages"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing pickup metadata: {error.args[0]}"
        ) from error

    platform = get_platform(profile.platform)
    items_engine = get_engine(profile.engine).items
    pickup_engine = get_engine(profile.engine).pickup
    locator_hex = profile.parameters.get(
        "pickup_table_locator", pickup_engine.PICKUP_TABLE_LOCATOR
    )
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = items_engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    if platform.read_overlay_decompressed is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
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
        "record_count": 1,
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "overlay_id": overlay_id,
            "table_offset": table_offset,
        },
        "level_ranges": level_ranges,
    }
