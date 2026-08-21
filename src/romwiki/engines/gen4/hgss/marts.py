from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.engines.gen4.shared.script_table import parse_script_table
from romwiki.schema import RecordProvenance, Shop
from romwiki.util.byte_search import find_unique_pattern
from romwiki.util.errors import InvalidRomError

# HGSS's field-script mart-opening dispatch commands (`gen4/hgss/
# script_opcode_table.py`'s pret/pokeheartgold-derived opcodes 0x113-0x116)
# -- verified real and location-attachable against the real HeartGold ROM's
# script archive: 65 dispatch sites across the whole script archive, every
# owning map header a real, correctly-named location (Goldenrod City,
# Celadon City's four separate department-store-floor scripts, Pokéathlon
# Dome, Olivine City, Route 32/40, Pokémon League, Battle Frontier -- not a
# single implausible hit).
#
# What is NOT decoded: the inventory *content* each dispatch command
# references. DPPT's equivalent commands resolve to real item lists via two
# ARM9-embedded structures -- an ARM9 pointer table of 0xFFFF-terminated
# item lists for `specialty`/`decoration`/`seal` marts
# (`gen4/dppt/marts.py`'s `parse_specialty_mart_inventories`), and a single
# badge-tiered (item_id, tier) list terminated by (0, 0) for `common` marts
# (`parse_common_mart_inventory`). An exhaustive, mechanical byte-pattern
# search for both exact structures across HGSS's entire ARM9 binary *and*
# all 129 ARM9 overlays found zero candidate matches of any length -- not a
# "didn't look hard enough" gap, but a real negative result: HGSS encodes
# this content differently (or somewhere this search didn't cover), and
# guessing at an unproven structure would violate this project's evidence
# bar. `LocationMartReference` (see schema/locations.py) publishes what IS
# proven -- the dispatch command's kind, raw inventory selector, and real
# map-header location -- without inventing item contents.
#
# A script-variable-supplied inventory selector (>= 0x8000, the same
# variable-ID boundary every other Gen IV scanner in this codebase uses) is
# excluded rather than reported as a literal, matching every other
# reachable-facts scanner's convention.
MART_BUY_COMMAND = 0x0113
SPECIAL_MART_BUY_COMMAND = 0x0114
DECORATION_MART_COMMAND = 0x0115
SEAL_MART_COMMAND = 0x0116
_MART_DISPATCH_KINDS = {
    MART_BUY_COMMAND: "common",
    SPECIAL_MART_BUY_COMMAND: "specialty",
    DECORATION_MART_COMMAND: "decoration",
    SEAL_MART_COMMAND: "seal",
}
_INVENTORY_SELECTOR_VARIABLE_MINIMUM = 0x8000


@dataclass(frozen=True, slots=True)
class Gen4HgssMartDispatchCommand:
    offset: int
    kind: str
    inventory_id: int


def parse_mart_dispatch_commands(
    data: bytes,
) -> tuple[Gen4HgssMartDispatchCommand, ...]:
    """Find HGSS mart-opening dispatch commands with a literal inventory selector.

    See the module-level comment above for the verification rationale and
    what this deliberately does not decode.
    """
    code_offset = parse_script_table(data)
    commands = []
    for offset in range(code_offset, len(data) - 3):
        opcode = struct.unpack_from("<H", data, offset)[0]
        kind = _MART_DISPATCH_KINDS.get(opcode)
        if kind is None:
            continue
        inventory_id = struct.unpack_from("<H", data, offset + 2)[0]
        if inventory_id >= _INVENTORY_SELECTOR_VARIABLE_MINIMUM:
            continue
        commands.append(
            Gen4HgssMartDispatchCommand(
                offset=offset, kind=kind, inventory_id=inventory_id
            )
        )
    return tuple(commands)


# `hgssShopNames`/`getShopNames(Type_HGSS)` (Ajarmar/universal-pokemon-
# randomizer-zx's `Gen4Constants.java`) -- an HGSS-specific array, distinct
# from that same file's separate `ptShopNames`/`dpShopNames`. Several of its
# labels ("Veilstone Department Store...", "Sunyshore Market Seals...",
# "Pokeathlon Dome...") name Sinnoh locations that don't exist in HGSS's
# Johto/Kanto setting; those are the tool's own placeholder names for shared
# byte-table slots that hold no valid HGSS data, not real in-game shops.
# `SKIPPED_SHOP_IDS` excludes exactly those slots (plus index 28, the array's
# own "Unused Secondary" label, and 37/39), verified against the real
# HeartGold ROM: every skipped slot's real item-ID data is either absent or
# structurally implausible, while every published (non-skipped) slot decodes
# to real, in-bounds item IDs under a real Johto/Kanto location name.
# `MAIN_GAME_SHOP_IDS` is cross-checked against real HGSS game structure:
# every included ID is a Johto shop reachable before the Elite Four; every
# excluded ID is either Kanto (post-Elite-Four-only, e.g. every Celadon
# Department Store floor) or a story-gated variant superseded by another
# entry (e.g. "Mahogany Before Hideout" is excluded in favor of "Mahogany
# After Hideout").
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
