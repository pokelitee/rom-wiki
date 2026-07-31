from __future__ import annotations

import struct
from collections.abc import Sequence

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
