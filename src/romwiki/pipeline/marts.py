from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import MARTS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_mart_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for mart extraction")
    profile = result.match.profile
    if "shop_items" in profile.layout:
        return _extract_archive_marts(result)
    try:
        messages_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
        shop_item_overlay_id = profile.parameters["shop_item_overlay_id"]
        shop_item_offsets = tuple(profile.parameters["shop_item_offsets"])
        shop_item_sizes = tuple(profile.parameters["shop_item_sizes"])
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing mart metadata: {error.args[0]}"
        ) from error
    tm_shop_ids = frozenset(profile.parameters.get("tm_shop_ids", ()))
    regular_shop_ids = frozenset(profile.parameters.get("regular_shop_ids", ()))

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).marts
    items_engine = get_engine(profile.engine).items
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = items_engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    overlay, overlay_data = platform.read_overlay_decompressed(
        result.image, shop_item_overlay_id
    )
    shops = engine.parse_shop_catalog(
        overlay_data,
        shop_item_offsets=shop_item_offsets,
        shop_item_sizes=shop_item_sizes,
        tm_shop_ids=tm_shop_ids,
        regular_shop_ids=regular_shop_ids,
        archive_path=f"overlay{shop_item_overlay_id}",
    )
    records = [
        {
            **{
                key: value for key, value in shop.to_dict().items() if key != "item_ids"
            },
            "items": [
                {"item_id": item_id, "name": item_names[item_id]}
                for item_id in shop.item_ids
            ],
        }
        for shop in shops
    ]
    return {
        "schema_version": MARTS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "marts",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "shop_item_overlay": {
                "id": shop_item_overlay_id,
                "file_id": overlay.file_id,
            },
            "item_names": {"archive": messages_path, "member": item_names_member},
        },
        "records": records,
    }


def write_mart_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)


def _extract_archive_marts(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        messages_path = profile.layout["messages"]
        shop_path = profile.layout["shop_items"]
        item_names_member = profile.parameters["item_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing archive mart metadata: {error.args[0]}"
        ) from error
    platform = get_platform(profile.platform)
    filesystem = platform.filesystem_from_image(result.image)
    shops = platform.archive_cls.from_bytes(filesystem.read(shop_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    items_engine = get_engine(profile.engine).items
    item_names = items_engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    engine = get_engine(profile.engine).marts
    catalog = engine.parse_archive_shop_catalog(
        tuple(shops.read(index) for index in range(len(shops.members))),
        archive_path=shop_path,
    )
    records = [
        {
            **{
                key: value for key, value in shop.to_dict().items() if key != "item_ids"
            },
            "items": [
                {"item_id": item_id, "name": item_names[item_id]}
                for item_id in shop.item_ids
            ],
        }
        for shop in catalog
    ]
    return {
        "schema_version": MARTS_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "marts",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "shop_items": {"archive": shop_path},
            "item_names": {"archive": messages_path, "member": item_names_member},
        },
        "records": records,
    }
