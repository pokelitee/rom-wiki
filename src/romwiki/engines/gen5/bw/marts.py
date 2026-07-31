from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.schema import RecordProvenance, Shop

from .disassembler import disassemble_function

# `ShopItemOffsets`/`ShopItemSizes` (gen5_offsets.ini, `[Black (U)]`/
# `[White (U)]`): one persistent item list per location-specific shop,
# including TM shops but excluding the dynamic plain Poké Marts, stored as
# consecutive item-ID
# words at a literal byte offset in the (BLZ-compressed) `ShopItemOvlNumber`
# overlay. See sites/games/black-white/wiki/data-sources.md for the source
# and verification.
SHOP_ITEM_WORD_SIZE = 2

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
_SHOP_SELECTOR_VARIABLE = 0x8000
_SHOP_MODE_VARIABLE = 0x8001
_SHOP_GLOBAL_SCRIPT_ID = 10110
STANDARD_SHOP_SELECTOR = 255


@dataclass(frozen=True, slots=True)
class Gen5ShopDispatch:
    selector_id: int
    mode: int
    command_offset: int


def parse_shop_dispatch(
    script: bytes, function_offset: int
) -> Gen5ShopDispatch | None:
    """Decode a local function that invokes BW1's global shop dispatcher."""
    selector_id = None
    mode = None
    for instruction in sorted(
        disassemble_function(script, function_offset).values(),
        key=lambda value: value.offset,
    ):
        if instruction.name in {"WorkSet", "WorkSetConst"}:
            variable, value = instruction.params
            if variable == _SHOP_SELECTOR_VARIABLE:
                selector_id = value
            elif variable == _SHOP_MODE_VARIABLE:
                mode = value
        elif (
            instruction.name == "RTCallGlobal"
            and instruction.params == (_SHOP_GLOBAL_SCRIPT_ID,)
            and selector_id is not None
            and mode is not None
        ):
            return Gen5ShopDispatch(
                selector_id=selector_id,
                mode=mode,
                command_offset=instruction.offset,
            )
    return None


def parse_shop_catalog(
    overlay_data: bytes,
    *,
    shop_item_offsets: tuple[int, ...],
    shop_item_sizes: tuple[int, ...],
    tm_shop_ids: frozenset[int],
    regular_shop_ids: frozenset[int],
    archive_path: str,
) -> tuple[Shop, ...]:
    """Decode every location-specific shop's persistent item stock.

    Plain Poké Marts are skipped because their stock is selected dynamically
    by badge count. TM shops use the same overlay tables as specialty shops
    and are retained.
    """
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
