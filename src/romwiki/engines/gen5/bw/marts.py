from __future__ import annotations

import struct

from romwiki.engines.gen5.shared.vendors import (
    Gen5SpecialVendor,
    Gen5SpecialVendorItem,
    fixed_vendor_items,
)
from romwiki.schema import RecordProvenance, Shop
from romwiki.util.byte_search import find_unique_pattern

# `ShopItemOffsets`/`ShopItemSizes` (gen5_offsets.ini, `[Black (U)]`/
# `[White (U)]`): one persistent item list per location-specific shop,
# including TM shops but excluding the dynamic plain Poké Marts, stored as
# consecutive item-ID
# words at a literal byte offset in the (BLZ-compressed) `ShopItemOvlNumber`
# overlay. See sites/games/black-white/wiki/data-sources.md for the source
# and verification.
SHOP_CATALOG_LOCATOR = "00A00F0000000000260A010000000000"
SHOP_RELATIVE_OFFSETS = (
    0x0,
    0x4,
    0xE,
    0x14,
    0x2C,
    0x58,
    0xAC,
    0xBA,
    0xC8,
    0xD8,
    0xE8,
    0xF8,
    0x108,
    0x118,
    0x12A,
    0x13C,
    0x14E,
    0x164,
    0x17A,
    0x190,
    0x1C0,
    0x1DC,
    0x1FC,
    0x23C,
    0x25E,
    0x282,
)
SHOP_ITEM_SIZES = (
    2,
    2,
    3,
    4,
    4,
    6,
    7,
    7,
    8,
    8,
    8,
    8,
    8,
    9,
    9,
    9,
    11,
    11,
    11,
    11,
    14,
    16,
    16,
    17,
    18,
    19,
)
TM_SHOP_IDS = frozenset({1, 2, 4, 7})
REGULAR_SHOP_IDS = frozenset({0, 16, 20, 23, 24, 25})

# `bw1ShopNames`/`bw1MainGameShops` (Gen5Constants.java): fixed internal shop
# labels and which are part of the main game (as opposed to post-game-only),
# identical between Black and White since both share the same shop layout
# (only their item-table byte offsets and TM/regular shop index lists differ
# per version). Index matches `ShopItemOffsets`/`ShopItemSizes` directly.
SHOP_NAMES = (
    "Primary 0 Badges",
    "Shopping Mall 9 TMs",
    "Icirrus Secondary (TMs)",
    "Driftveil Herb Salesman",
    "Mistralton Secondary (TMs)",
    "Shopping Mall 9 F3 Left",
    "Accumula Secondary",
    "Nimbasa Secondary (TMs)",
    "Striaton Secondary",
    "League Secondary",
    "Lacunosa Secondary",
    "Black City/White Forest Secondary",
    "Nacrene/Shopping Mall 9 X Items",
    "Driftveil Incense Salesman",
    "Nacrene Secondary",
    "Undella Secondary",
    "Primary 2 Badges",
    "Castelia Secondary",
    "Driftveil Secondary",
    "Opelucid Secondary",
    "Primary 3 Badges",
    "Shopping Mall 9 F1",
    "Shopping Mall 9 F2",
    "Primary 5 Badges",
    "Primary 7 Badges",
    "Primary 8 Badges",
)
MAIN_GAME_SHOP_IDS = frozenset({3, 5, 6, 8, 9, 12, 14, 17, 18, 19, 21, 22})

SHOP_SELECTOR_TO_INVENTORY_ID = {
    0: 6,
    1: 8,
    2: 14,
    3: 17,
    4: 7,
    5: 18,
    6: 4,
    7: 2,
    8: 19,
    9: 9,
    10: 10,
    11: 15,
    12: 11,
    13: 12,
    14: 3,
    15: 13,
    16: 21,
    17: 1,
    18: 22,
    19: 5,
}
_BW_BP_TM_ITEMS = (
    (350, 36),
    (375, 36),
    (414, 36),
    (415, 36),
    (361, 48),
    (378, 48),
    (386, 48),
    (387, 48),
    (391, 48),
    (404, 48),
)
_BW_BP_ITEM_ITEMS = (
    *((item_id, 1) for item_id in (46, 49, 47, 52, 48, 45)),
    *((item_id, 16) for item_id in (289, 290, 291, 292, 293, 294, 272, 273)),
    *((item_id, 32) for item_id in (214, 271, 545, 546, 542, 547)),
    *(
        (item_id, 48)
        for item_id in (
            267,
            297,
            232,
            276,
            265,
            266,
            230,
            220,
            287,
            275,
            326,
            327,
            213,
            270,
            278,
            541,
            544,
            50,
        )
    ),
)

_BLACK_CITY_MARKET_ITEMS = (
    Gen5SpecialVendorItem(30, 1000, "Current resident: Robbie"),
    Gen5SpecialVendorItem(43, 1500, "Current resident: Shane"),
    Gen5SpecialVendorItem(74, 3000, "Current resident: Collin"),
    Gen5SpecialVendorItem(75, 3000, "Current resident: Marie"),
    Gen5SpecialVendorItem(73, 3000, "Current resident: Eliza"),
    Gen5SpecialVendorItem(72, 3000, "Current resident: Doug"),
    Gen5SpecialVendorItem(86, 3000, "Current resident: Dave"),
    Gen5SpecialVendorItem(77, 5000, "Current resident: Miki"),
    Gen5SpecialVendorItem(88, 6000, "Current resident: Silvia"),
    Gen5SpecialVendorItem(109, 10000, "Current resident: Grace"),
    Gen5SpecialVendorItem(80, 10000, "Current resident: Lena"),
    Gen5SpecialVendorItem(107, 10000, "Current resident: Molly"),
    Gen5SpecialVendorItem(85, 10000, "Current resident: Karenna"),
    Gen5SpecialVendorItem(84, 10000, "Current resident: Ralph"),
    Gen5SpecialVendorItem(82, 10000, "Current resident: Vincent"),
    Gen5SpecialVendorItem(110, 10000, "Current resident: Carlos"),
    Gen5SpecialVendorItem(83, 10000, "Current resident: Ken"),
    Gen5SpecialVendorItem(108, 10000, "Current resident: Herman"),
    Gen5SpecialVendorItem(81, 10000, "Current resident: Rosa"),
    Gen5SpecialVendorItem(4, 10000, "Current resident: Pierce"),
    Gen5SpecialVendorItem(90, 10000, "Current resident: Leo"),
    Gen5SpecialVendorItem(93, 10000, "Current resident: Lynette"),
    Gen5SpecialVendorItem(64, 15000, "Current resident: Emi"),
    Gen5SpecialVendorItem(63, 18000, "Current resident: Jacques"),
    Gen5SpecialVendorItem(87, 20000, "Current resident: Gene"),
    Gen5SpecialVendorItem(106, 30000, "Current resident: Britney"),
    Gen5SpecialVendorItem(89, 38000, "Current resident: Miho"),
    Gen5SpecialVendorItem(91, 48000, "Current resident: Piper"),
    Gen5SpecialVendorItem(92, 50000, "Current resident: Ryder"),
    Gen5SpecialVendorItem(11, 50000, "Current resident: Frederic"),
)


def resolve_special_vendor(selector_id: int) -> Gen5SpecialVendor | None:
    """Resolve dispatcher selectors whose semantics are not ordinary marts."""
    if 247 <= selector_id <= 251:
        return Gen5SpecialVendor(
            selector_id=selector_id,
            name="Black City resident market",
            kind="market",
            currency="money",
            items=_BLACK_CITY_MARKET_ITEMS,
            availability="Post-game; the market appears with at least 4 residents.",
            is_main_game=False,
            vendor_id="black-city-resident-market",
            selector_ids=tuple(range(247, 252)),
        )
    if selector_id == 253:
        return Gen5SpecialVendor(
            selector_id=selector_id,
            name="Battle Point TM exchange",
            kind="exchange",
            currency="bp",
            items=fixed_vendor_items(_BW_BP_TM_ITEMS),
            is_main_game=True,
        )
    if selector_id == 254:
        return Gen5SpecialVendor(
            selector_id=selector_id,
            name="Battle Point item exchange",
            kind="exchange",
            currency="bp",
            items=fixed_vendor_items(_BW_BP_ITEM_ITEMS),
            is_main_game=True,
        )
    return None


def parse_shop_catalog(
    overlay_data: bytes,
    *,
    archive_path: str,
    shop_item_offsets: tuple[int, ...] | None = None,
    shop_item_sizes: tuple[int, ...] = SHOP_ITEM_SIZES,
    tm_shop_ids: frozenset[int] = TM_SHOP_IDS,
    regular_shop_ids: frozenset[int] = REGULAR_SHOP_IDS,
) -> tuple[Shop, ...]:
    """Decode every location-specific shop's persistent item stock.

    Plain Poké Marts are skipped because their stock is selected dynamically
    by badge count. TM shops use the same overlay tables as specialty shops
    and are retained.
    """
    if shop_item_offsets is None:
        locator = bytes.fromhex(SHOP_CATALOG_LOCATOR)
        base_offset = find_unique_pattern(
            overlay_data, locator, label="the BW shop catalog"
        ) + len(locator)
        shop_item_offsets = tuple(
            base_offset + relative_offset for relative_offset in SHOP_RELATIVE_OFFSETS
        )
    shops = []
    for shop_id, (offset, size) in enumerate(
        zip(shop_item_offsets, shop_item_sizes, strict=True)
    ):
        if shop_id in regular_shop_ids:
            continue
        item_ids = struct.unpack_from(f"<{size}H", overlay_data, offset)
        shops.append(
            Shop(
                shop_id=shop_id,
                name=SHOP_NAMES[shop_id],
                kind="tm" if shop_id in tm_shop_ids else "specialty",
                is_main_game=shop_id in MAIN_GAME_SHOP_IDS,
                item_ids=item_ids,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=shop_id
                ),
            )
        )
    return tuple(shops)
