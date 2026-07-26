from __future__ import annotations

import struct

from romwiki.schema import Gen5Shop, RecordProvenance

# `ShopItemOffsets`/`ShopItemSizes` (gen5_offsets.ini, `[Black (U)]`/
# `[White (U)]`): one persistent item list per "specialty" shop (everything
# except the TM shops and the plain Poké Marts, whose stock is a fixed
# generation-wide item list, not ROM data), stored as consecutive item-ID
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


def parse_shop_catalog(
    overlay_data: bytes,
    *,
    shop_item_offsets: tuple[int, ...],
    shop_item_sizes: tuple[int, ...],
    tm_shop_ids: frozenset[int],
    regular_shop_ids: frozenset[int],
    archive_path: str,
) -> tuple[Gen5Shop, ...]:
    """Decode every "specialty" shop's persistent item stock.

    TM shops and plain Poké Marts (`tm_shop_ids`/`regular_shop_ids`) are
    skipped entirely: their stock isn't a ROM-stored table at all (it's a
    fixed, generation-wide item list -- the same list PokeDB and every other
    Gen5 game already document -- so there's nothing here to decode).
    """
    shops = []
    for shop_id, (offset, size) in enumerate(
        zip(shop_item_offsets, shop_item_sizes, strict=True)
    ):
        if shop_id in tm_shop_ids or shop_id in regular_shop_ids:
            continue
        item_ids = struct.unpack_from(f"<{size}H", overlay_data, offset)
        shops.append(
            Gen5Shop(
                shop_id=shop_id,
                name=SHOP_NAMES[shop_id],
                is_main_game=shop_id in MAIN_GAME_SHOP_IDS,
                item_ids=item_ids,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=shop_id
                ),
            )
        )
    return tuple(shops)
