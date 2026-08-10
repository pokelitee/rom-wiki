from __future__ import annotations

import struct

from romwiki.schema import RecordProvenance, Shop
from romwiki.util.byte_search import find_unique_pattern
from romwiki.util.errors import InvalidRomError

SHOP_COUNT = 40
SKIPPED_SHOP_IDS = frozenset({17, 18, 22, 23, 24, 25, 26, 27, 28, 29, 30, 37, 39})
MAIN_GAME_SHOP_IDS = frozenset({0, 2, 5, 6, 7, 12, 14, 16, 19, 31, 33, 34, 36})
SHOP_NAMES = (
    "Cherrygrove Secondary",
    "Cerulean Secondary",
    "Ecruteak Secondary",
    "Celadon Department Store Mail",
    "Saffron Secondary",
    "Violet Secondary",
    "Blackthorn Secondary",
    "Olivine Secondary",
    "Fuchsia Secondary",
    "Lavender Secondary",
    "Pewter Secondary",
    "Viridian Secondary",
    "Azalea Secondary",
    "Mahogany Before Hideout",
    "Safari Zone Gate Southwest",
    "Goldenrod Herb Shop",
    "Cianwood Pharmacy",
    "Veilstone Department Store Secret Base Decorations 1",
    "Veilstone Department Store Secret Base Decorations 2",
    "Goldenrod Department Store Vitamins",
    "Celadon Department Store Vitamins",
    "Mt. Moon Square",
    "Sunyshore Market Seals 1",
    "Sunyshore Market Seals 2",
    "Sunyshore Market Seals 3",
    "Sunyshore Market Seals 4",
    "Sunyshore Market Seals 5",
    "Sunyshore Market Seals 6",
    "Unused Secondary",
    "Sunyshore Market Seals 7",
    "Pokeathlon Dome Data Card Shop 25-27",
    "Goldenrod Department Store X Items",
    "Celadon Department Store X Items",
    "Mahogany After Hideout",
    "Goldenrod Department Store Healing",
    "Celadon Department Store Healing",
    "Goldenrod Department Store Balls Etc.",
    "Goldenrod TMs",
    "Celadon Department Store Balls Etc.",
    "Celadon TMs",
)


def parse_shop_catalog(
    data: bytes, *, locator: bytes, archive_path: str, item_count: int
) -> tuple[Shop, ...]:
    cursor = find_unique_pattern(data, locator, label="the HGSS shop catalog") + len(
        locator
    )
    shops = []
    for shop_id in range(SHOP_COUNT):
        item_ids = []
        while cursor + 2 <= len(data):
            item_id = struct.unpack_from("<H", data, cursor)[0]
            cursor += 2
            if item_id == 0xFFFF:
                break
            if shop_id not in SKIPPED_SHOP_IDS and item_id and item_id >= item_count:
                raise InvalidRomError(
                    f"HGSS shop {shop_id} references invalid item {item_id}"
                )
            if item_id:
                item_ids.append(item_id)
        else:
            raise InvalidRomError(f"HGSS shop {shop_id} is unterminated")
        if shop_id in SKIPPED_SHOP_IDS:
            continue
        shops.append(
            Shop(
                shop_id=shop_id,
                name=SHOP_NAMES[shop_id],
                kind="specialty",
                is_main_game=shop_id in MAIN_GAME_SHOP_IDS,
                item_ids=tuple(item_ids),
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=shop_id
                ),
            )
        )
    return tuple(shops)
