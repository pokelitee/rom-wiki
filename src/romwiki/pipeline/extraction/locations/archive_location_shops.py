from __future__ import annotations

from typing import Any

from romwiki.engines.registry import LOCATION_SPECIAL_VENDORS, get_engine
from romwiki.pipeline.extraction.locations.archive_encounter_map_source import (
    ArchiveLocationCatalogs,
    ArchiveLocationSource,
)
from romwiki.schema import (
    LocationShop,
    LocationShopItem,
)
from romwiki.util.errors import DataSourceError


def extract_script_shops(
    source: ArchiveLocationSource,
    catalogs: ArchiveLocationCatalogs,
    script_file_id: int,
) -> tuple[list[LocationShop], set[str], list[int]]:
    shops: list[LocationShop] = []
    seen_vendor_ids: set[str] = set()
    unsupported_shop_selectors: list[int] = []
    if script_file_id >= len(source.scripts.members):
        return shops, seen_vendor_ids, unsupported_shop_selectors

    script = source.scripts.read(script_file_id)
    seen_dispatches = set()
    for function_offset in source.engine.parse_function_offsets(script):
        dispatch = source.engine.parse_shop_dispatch(script, function_offset)
        if dispatch is None:
            continue
        dispatch_key = (dispatch.selector_id, dispatch.command_offset)
        if dispatch_key in seen_dispatches:
            continue
        seen_dispatches.add(dispatch_key)
        inventory_id = source.engine.SHOP_SELECTOR_TO_INVENTORY_ID.get(
            dispatch.selector_id
        )
        if inventory_id is not None:
            catalog_shop = catalogs.shops_by_id.get(inventory_id)
            if catalog_shop is not None:
                shops.append(
                    _build_catalog_shop(
                        catalog_shop,
                        catalogs.item_prices_by_id,
                        inventory_id=inventory_id,
                        script_file_id=script_file_id,
                        dispatch=dispatch,
                    )
                )
            continue

        special_vendor = source.engine.resolve_special_vendor(dispatch.selector_id)
        if special_vendor is not None:
            if (
                special_vendor.vendor_id is None
                or special_vendor.vendor_id not in seen_vendor_ids
            ):
                shops.append(
                    _build_special_vendor_shop(
                        special_vendor,
                        catalogs.item_names_by_id,
                        script_file_id=script_file_id,
                        command_offset=dispatch.command_offset,
                        selector_id=dispatch.selector_id,
                        mode=dispatch.mode,
                    )
                )
                if special_vendor.vendor_id is not None:
                    seen_vendor_ids.add(special_vendor.vendor_id)
            continue
        if dispatch.selector_id != source.engine.STANDARD_SHOP_SELECTOR:
            unsupported_shop_selectors.append(dispatch.selector_id)
            continue
        shops.append(_build_standard_mart_shop(script_file_id, dispatch))
    return shops, seen_vendor_ids, unsupported_shop_selectors


def extract_location_vendors(
    source: ArchiveLocationSource,
    header_id: int,
    item_names_by_id: dict[int, str],
    script_file_id: int,
    seen_vendor_ids: set[str],
) -> list[LocationShop]:
    if LOCATION_SPECIAL_VENDORS not in get_engine(source.profile.engine).capabilities:
        return []

    shops = []
    for special_vendor in source.engine.resolve_location_special_vendors(header_id):
        if (
            special_vendor.vendor_id is not None
            and special_vendor.vendor_id in seen_vendor_ids
        ):
            continue
        shops.append(
            _build_special_vendor_shop(
                special_vendor,
                item_names_by_id,
                script_file_id=script_file_id,
                command_offset=-1,
            )
        )
        if special_vendor.vendor_id is not None:
            seen_vendor_ids.add(special_vendor.vendor_id)
    return shops


def _build_standard_mart_shop(script_file_id: int, dispatch: Any) -> LocationShop:
    return LocationShop(
        kind="common",
        currency="money",
        inventory_id=dispatch.selector_id,
        script_file_id=script_file_id,
        command_offset=dispatch.command_offset,
        items=(),
        name="Standard Poké Mart",
        is_main_game=True,
        selector_id=dispatch.selector_id,
        mode=dispatch.mode,
        dynamic=True,
        inventory_source="runtime",
        availability="Stock changes with badge progression.",
    )


def _build_catalog_shop(
    catalog_shop: dict[str, Any],
    item_prices_by_id: dict[int, int | None],
    *,
    inventory_id: int,
    script_file_id: int,
    dispatch: Any,
) -> LocationShop:
    return LocationShop(
        kind=catalog_shop["kind"],
        currency="money",
        inventory_id=inventory_id,
        script_file_id=script_file_id,
        command_offset=dispatch.command_offset,
        items=tuple(
            LocationShopItem(
                item_id=item["item_id"],
                name=item["name"],
                price=item_prices_by_id.get(item["item_id"]),
                required_badges=None,
            )
            for item in catalog_shop["items"]
        ),
        name=catalog_shop["name"],
        is_main_game=catalog_shop["is_main_game"],
        selector_id=dispatch.selector_id,
        mode=dispatch.mode,
        inventory_source="rom-catalog",
    )


def _build_special_vendor_shop(
    vendor: Any,
    item_names_by_id: dict[int, str],
    *,
    script_file_id: int,
    command_offset: int,
    selector_id: int | None = None,
    mode: int | None = None,
) -> LocationShop:
    missing_item_ids = [
        item.item_id for item in vendor.items if item.item_id not in item_names_by_id
    ]
    if missing_item_ids:
        source = f"selector {selector_id}" if selector_id is not None else vendor.name
        raise DataSourceError(
            f"Special vendor {source} references unknown items: {missing_item_ids}"
        )
    selector_ids = vendor.selector_ids
    if not selector_ids and selector_id is not None:
        selector_ids = (selector_id,)
    return LocationShop(
        kind=vendor.kind,
        currency=vendor.currency,
        inventory_id=None,
        script_file_id=script_file_id,
        command_offset=command_offset,
        items=tuple(
            LocationShopItem(
                item_id=item.item_id,
                name=item_names_by_id[item.item_id],
                price=item.price,
                required_badges=None,
                availability=item.availability,
            )
            for item in vendor.items
        ),
        name=vendor.name,
        is_main_game=vendor.is_main_game,
        selector_id=selector_id,
        mode=mode,
        dynamic=vendor.dynamic,
        inventory_source="runtime" if vendor.dynamic else "engine-rule",
        availability=vendor.availability,
        vendor_id=vendor.vendor_id,
        selector_ids=selector_ids,
    )
