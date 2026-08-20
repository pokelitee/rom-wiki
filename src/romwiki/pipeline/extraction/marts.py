from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.map_headers import read_code_binary
from romwiki.platforms.registry import get_platform
from romwiki.schema.datasets import dataset_envelope
from romwiki.schema.versions import MARTS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


def _shop_records(
    shops: Sequence[Any], item_names: Sequence[str]
) -> list[dict[str, Any]]:
    return [
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


def extract_mart_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for mart extraction")
    profile = result.match.profile
    if "shop_items" in profile.layout:
        return _extract_archive_marts(result)
    if "shop_catalog_locator" in profile.parameters:
        return _extract_arm9_marts(result)
    try:
        messages_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
        shop_item_overlay_id = profile.parameters["shop_item_overlay_id"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing mart metadata: {error.args[0]}"
        ) from error
    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).marts
    items_engine = get_engine(profile.engine).items
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    item_names = items_engine.parse_english_message_archive(
        messages.read(item_names_member)
    )
    if platform.read_overlay_decompressed is None:
        raise ProfileError(f"Platform {profile.platform!r} does not support overlays")
    overlay, overlay_data = platform.read_overlay_decompressed(
        result.image, shop_item_overlay_id
    )
    shops = engine.parse_shop_catalog(
        overlay_data,
        archive_path=f"overlay{shop_item_overlay_id}",
    )
    records = _shop_records(shops, item_names)
    return dataset_envelope(
        schema_version=MARTS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="marts",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "shop_item_overlay": {
                "id": shop_item_overlay_id,
                "file_id": overlay.file_id,
            },
            "item_names": {"archive": messages_path, "member": item_names_member},
        },
        records=records,
    )


def _extract_arm9_marts(result: InspectionResult) -> dict[str, Any]:
    assert result.match is not None
    profile = result.match.profile
    try:
        locator = bytes.fromhex(profile.parameters["shop_catalog_locator"])
        messages_path = profile.layout["messages"]
        item_names_member = profile.parameters["item_names_member"]
    except (KeyError, ValueError) as error:
        raise ProfileError(f"Profile {profile.id} has invalid mart metadata") from error

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).marts
    filesystem = platform.filesystem_from_image(result.image)
    messages = platform.archive_cls.from_bytes(
        filesystem.read(messages_path),
        allow_truncated=profile.parameters.get("messages_allow_truncated", False),
    )
    item_names = engine.parse_english_message_archive(messages.read(item_names_member))
    arm9_data = read_code_binary(platform, result.image, engine)
    shops = engine.parse_shop_catalog(
        arm9_data,
        locator=locator,
        archive_path="arm9",
        item_count=len(item_names),
    )
    records = _shop_records(shops, item_names)
    return dataset_envelope(
        schema_version=MARTS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="marts",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "shop_catalog": {"archive": "arm9", "locator": locator.hex()},
            "item_names": {"archive": messages_path, "member": item_names_member},
        },
        records=records,
    )


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
    records = _shop_records(catalog, item_names)
    return dataset_envelope(
        schema_version=MARTS_RAW_SCHEMA_VERSION,
        game=profile.id,
        engine=profile.engine,
        dataset="marts",
        source={
            "rom_sha256": result.image.hashes.sha256,
            "shop_items": {"archive": shop_path},
            "item_names": {"archive": messages_path, "member": item_names_member},
        },
        records=records,
    )
