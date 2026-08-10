from __future__ import annotations

import struct
from collections.abc import Sequence

from romwiki.engines.gen5.vendors import (
    Gen5SpecialVendor,
    Gen5SpecialVendorItem,
    fixed_vendor_items,
)
from romwiki.schema import RecordProvenance, Shop
from romwiki.util.errors import InvalidRomError

SHOP_NAMES = (
    "Primary 0 Badges",
    "Primary 1 Badge",
    "Primary 3 Badges",
    "Primary 5 Badges",
    "Primary 7 Badges",
    "Primary 8 Badges",
    "Accumula Secondary",
    "Striaton Secondary (TMs)",
    "Nacrene Secondary",
    "Castelia Secondary",
    "Nimbasa Secondary (TMs)",
    "Driftveil Secondary",
    "Mistralton Secondary (TMs)",
    "Icirrus Secondary",
    "Opelucid Secondary",
    "Victory Road Secondary",
    "Pokemon League Secondary",
    "Lacunosa Secondary (TMs)",
    "Undella Secondary",
    "Black City/White Forest Secondary",
    "Nacrene/Shopping Mall 9 X Items",
    "Driftveil Herb Salesman",
    "Driftveil Incense Salesman",
    "Shopping Mall 9 F1",
    "Shopping Mall 9 TMs",
    "Shopping Mall 9 F2",
    "Shopping Mall 9 F3 Left",
    "Aspertia Secondary",
    "Virbank Secondary",
    "Humilau Secondary",
    "Floccesy Secondary",
    "Lentimas Secondary",
)
TM_SHOP_IDS = frozenset({7, 10, 12, 17, 24})
REGULAR_SHOP_IDS = frozenset({0, 1, 2, 3, 4, 5})
MAIN_GAME_SHOP_IDS = frozenset(
    {9, 11, 14, 15, 16, 18, 20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 31}
)

# Local dispatcher selectors cover the 26 location-specific inventories after
# the six badge-tier primary marts in a/2/8/2.
SHOP_SELECTOR_TO_INVENTORY_ID = {selector: selector + 6 for selector in range(26)}

_B2W2_BP_TM_ITEMS = (
    *((item_id, 6) for item_id in (344, 347, 359, 386)),
    *((item_id, 12) for item_id in (358, 406, 416)),
    *((item_id, 18) for item_id in (337, 350, 375, 402, 414, 415)),
    *((item_id, 24) for item_id in (361, 378, 387, 391, 404)),
)
_B2W2_BP_ITEM_ITEMS = (
    *((item_id, 1) for item_id in (46, 49, 47, 52, 48, 45)),
    *((item_id, 3) for item_id in (82, 83, 84, 85)),
    *((item_id, 8) for item_id in (232, 265, 266, 267, 326, 327, 544)),
    *((item_id, 12) for item_id in (213, 230, 276, 278, 541)),
    *(
        (item_id, 16)
        for item_id in (
            289,
            290,
            291,
            292,
            293,
            294,
            272,
            273,
            214,
            271,
            545,
            546,
            542,
            547,
        )
    ),
    *((item_id, 24) for item_id in (220, 297, 287, 275, 270, 50)),
)

_BLACK_CITY_HEADER_ID = 5
_BLACK_CITY_MARKET_STORES = (
    Gen5SpecialVendor(
        selector_id=None,
        name="Black City market store 1",
        kind="market",
        currency="money",
        items=(
            Gen5SpecialVendorItem(83, 10000, "Weekdays"),
            Gen5SpecialVendorItem(321, 10000, "Weekends"),
        ),
        availability="Unlocked after clearing Black Tower Area 2; one item per day.",
        is_main_game=False,
        vendor_id="black-city-market-store-1",
    ),
    Gen5SpecialVendor(
        selector_id=None,
        name="Black City market store 2",
        kind="market",
        currency="money",
        items=(
            Gen5SpecialVendorItem(82, 20000, "Weekdays"),
            Gen5SpecialVendorItem(233, 20000, "Weekends"),
        ),
        availability="Unlocked after clearing Black Tower Area 5; one item per day.",
        is_main_game=False,
        vendor_id="black-city-market-store-2",
    ),
    Gen5SpecialVendor(
        selector_id=None,
        name="Black City market store 3",
        kind="market",
        currency="money",
        items=(
            Gen5SpecialVendorItem(108, 40000, "Weekdays"),
            Gen5SpecialVendorItem(252, 40000, "Weekends"),
        ),
        availability="Unlocked after clearing Black Tower Area 8; one item per day.",
        is_main_game=False,
        vendor_id="black-city-market-store-3",
    ),
    Gen5SpecialVendor(
        selector_id=None,
        name="Black City market store 4",
        kind="market",
        currency="money",
        items=(
            Gen5SpecialVendorItem(109, 60000, "Weekdays"),
            Gen5SpecialVendorItem(324, 60000, "Weekends"),
        ),
        availability="Unlocked after clearing Black Tower Area 10; one item per day.",
        is_main_game=False,
        vendor_id="black-city-market-store-4",
    ),
)


def resolve_special_vendor(selector_id: int) -> Gen5SpecialVendor | None:
    if selector_id == 253:
        return Gen5SpecialVendor(
            selector_id=selector_id,
            name="Battle Point TM exchange",
            kind="exchange",
            currency="bp",
            items=fixed_vendor_items(_B2W2_BP_TM_ITEMS),
            is_main_game=True,
        )
    if selector_id == 254:
        return Gen5SpecialVendor(
            selector_id=selector_id,
            name="Battle Point item exchange",
            kind="exchange",
            currency="bp",
            items=fixed_vendor_items(_B2W2_BP_ITEM_ITEMS),
            is_main_game=True,
        )
    return None


def resolve_location_special_vendors(
    header_id: int,
) -> tuple[Gen5SpecialVendor, ...]:
    """Return finite conditional vendors not exposed by the shop dispatcher."""
    if header_id == _BLACK_CITY_HEADER_ID:
        return _BLACK_CITY_MARKET_STORES
    return ()


def parse_archive_shop_catalog(
    members: Sequence[bytes], *, archive_path: str
) -> tuple[Shop, ...]:
    if len(members) < len(SHOP_NAMES):
        raise InvalidRomError("B2W2 shop archive has too few members")
    shops = []
    for shop_id, name in enumerate(SHOP_NAMES):
        if shop_id in REGULAR_SHOP_IDS:
            continue
        data = members[shop_id]
        if len(data) % 2:
            raise InvalidRomError(f"B2W2 shop {shop_id} has an odd record size")
        item_ids = tuple(value[0] for value in struct.iter_unpack("<H", data))
        shops.append(
            Shop(
                shop_id=shop_id,
                name=name,
                kind="tm" if shop_id in TM_SHOP_IDS else "specialty",
                is_main_game=shop_id in MAIN_GAME_SHOP_IDS,
                item_ids=item_ids,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=shop_id
                ),
            )
        )
    return tuple(shops)
