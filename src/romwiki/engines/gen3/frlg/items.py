from __future__ import annotations

import struct

from romwiki.schema import Item, RecordProvenance
from romwiki.util.errors import InvalidRomError

from .constants import ITEM_RECORD_SIZE
from .text import decode_gen3_text

# Generation III's item struct (44 bytes, `struct Item` in the public
# pokefirered/pokeemerald decompilation), verified against the real FireRed
# and LeafGreen ROMs by decoding Master Ball (item 1: name, price=0,
# hold_effect=0) and Ultra Ball (item 2: name, price=1200), and cross-
# checking `field_pocket_id` against nine items spanning all five real Bag
# pockets (Potion/Antidote/Rare Candy/Repel -> 1, Bicycle/Town Map -> 2,
# Master/Ultra Ball -> 3, TM01 -> 4, Oran/Cheri Berry -> 5 -- an exact match
# for Items/Key Items/Balls/TMs & HMs/Berries, FireRed and LeafGreen's five
# real Bag pockets):
#   0x00-0x0D  name (14 bytes, Gen III text-encoded, 0xFF-terminated)
#   0x0E-0x0F  item_id (u16)
#   0x10-0x11  price (u16)
#   0x12       hold_effect_id
#   0x13       hold_effect_parameter
#   0x14-0x17  description pointer (ROM address to a Gen III text-encoded,
#              0xFF-terminated string -- see `item_description_pointer`)
#   0x18-0x19  unknown/importance (not decoded -- semantics unconfirmed)
#   0x1A       field_pocket_id (see verification above)
# Deliberately left undecoded: byte 0x1B (varies across items but doesn't
# correlate with pocket, type, or any other confirmed concept -- reporting
# a guessed meaning would violate this repo's evidence-based norm); bytes
# 0x1D-0x23 (a small integer at 0x20-0x23 and a real-looking ROM pointer at
# 0x24-0x27 in the two ball records checked, but neither varies across any
# item this session cross-checked with a genuinely different field-use
# behavior, so there isn't yet a verified way to turn either into a small
# `field_use_function_id`/`battle_use_function_id`).
#
# Generation III has neither Fling nor Pluck (both introduced in Generation
# IV), so `fling_effect_id`/`fling_power`/`pluck_effect_id` are zeroed
# below rather than decoded from anything -- there is no ROM field for them
# to come from. `party_effects` is left `None`: Generation III's party-menu
# item usage dispatches through a ROM code pointer (the description-pointer-
# adjacent fields above), not a decodable data table like Gen4/5's dedicated
# party-effects bitfield.
_NAME_SIZE = 14


def item_description_pointer(data: bytes) -> int:
    """Read one item record's description pointer (a GBA ROM address, or 0
    for items that display no description). Resolving and decoding the
    text it points to is the extraction layer's job, since it owns ROM I/O
    (same reasoning as `trainers.py`'s party pointer).
    """
    return struct.unpack_from("<I", data, 0x14)[0]


def item_name(data: bytes) -> str:
    """Decode one item record's inline name field (the first 14 bytes).

    Unlike every NDS engine, Generation III has no separate item-name table
    -- each item's display name is embedded directly in its own record.
    """
    return decode_gen3_text(data[:_NAME_SIZE])


def parse_item_record(
    data: bytes,
    *,
    item_id: int,
    archive_path: str,
) -> Item:
    if len(data) != ITEM_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen III item record {item_id} has size {len(data)}, "
            f"expected {ITEM_RECORD_SIZE}"
        )

    price = struct.unpack_from("<H", data, 0x10)[0]
    return Item(
        item_id=item_id,
        # No archive concept on this flat platform -- the item's own ID is
        # the only meaningful "member" identity available.
        data_archive_member=item_id,
        price=price,
        hold_effect_id=data[0x12],
        hold_effect_parameter=data[0x13],
        pluck_effect_id=0,
        fling_effect_id=0,
        fling_power=0,
        natural_gift_power=0,
        natural_gift_type_id=0,
        prevent_toss=False,
        selectable=False,
        field_pocket_id=data[0x1A],
        battle_pocket_mask=0,
        field_use_function_id=0,
        battle_use_function_id=0,
        party_use=False,
        party_effects=None,
        provenance=RecordProvenance(source="rom", archive=archive_path, member=item_id),
    )
