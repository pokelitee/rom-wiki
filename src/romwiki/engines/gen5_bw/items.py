from __future__ import annotations

import struct

from romwiki.schema import Gen5Item, Gen5ItemPartyEffects, RecordProvenance
from romwiki.util.errors import InvalidRomError

GEN5_ITEM_RECORD_SIZE = 36
# Gen5 stores price at 1/10th scale, unlike Gen4 (which stores it directly).
GEN5_ITEM_PRICE_SCALE = 10

# This generation's Bag has only 5 pockets (down from Gen4's 8 -- Poké Balls,
# Battle Items, and Mail were folded into the general "Items" pocket).
# Confirmed against Bulbapedia's "List of items by pocket in Pokémon Black
# and White" (see plan.md for the full item-by-item verification).
GEN5_ITEM_POCKET_NAMES = (
    "items",
    "medicine",
    "tm-hm",
    "berries",
    "key-items",
)

# Byte-identical to Gen4's own field-use function ID enumeration
# (`gen4_dppt.items.GEN4_ITEM_FIELD_USE_NAMES`); duplicated here since the
# two engines are independent modules. Extended with one new entry (25) for
# the Dowsing MCHN, this generation's Itemfinder replacement with no Gen4
# counterpart.
GEN5_ITEM_FIELD_USE_NAMES = (
    "none",
    "healing",
    "town-map",
    "explorer-kit",
    "bicycle",
    "journal",
    "tm-hm",
    "mail",
    "berry",
    "poffin-case",
    "pal-pad",
    "poke-radar",
    "sprayduck",
    "mulch",
    "honey",
    "vs-seeker",
    "old-rod",
    "good-rod",
    "super-rod",
    "bag-message",
    "evolution-stone",
    "escape-rope",
    "azure-flute",
    "vs-recorder",
    "gracidea",
    "dowsing-machine",
)

# Byte layout of the real `a/0/2/4` archive's 36-byte records (item ID ==
# archive member index directly -- no ARM9 item-to-member map, unlike Gen4).
# No public documentation or decompilation covers this format; see plan.md
# for the full verification writeup. The first 12 bytes are byte-identical
# to Gen4's own item record; everything from byte 13 on diverges, since Gen5
# replaced Gen4's one large party-effects bitfield with dedicated
# per-concept fields:
#   price: u16 @ 0, x10.  hold_effect_id: byte @ 2.  pluck_effect_id: byte @ 4.
#   fling_effect_id: byte @ 5.  fling_power: byte @ 6.
#   natural_gift_power: byte @ 7.
#   natural_gift_type_id: bits 0-4 of the u16 @ 8 -- 0x1F ("no type") for
#     every non-berry item; real berries carry a real `TYPE_NAMES` index.
#   field_pocket_id: bits 7-10 of the same u16 -- see `GEN5_ITEM_POCKET_NAMES`.
#   field_use_function_id: byte @ 10 -- see `GEN5_ITEM_FIELD_USE_NAMES`.
#   battle_use_function_id: byte @ 11 -- a raw ID, not otherwise named
#     (matching Gen4's own precedent).
#   party_use: bool @ 12 -- true for anything that targets a specific party
#     member when used.
# party_effects (only when party_use is true) -- Gen5ItemPartyEffects:
#   heal_sleep/heal_poison/heal_burn/heal_freeze/heal_paralysis/
#     heal_confusion: bits 0-5 of the byte @ 16 (never infatuation -- no
#     item cures that in any generation).
#   revive/revive_all/level_up: bits 0/1/2 of the byte @ 17. NOT independent
#     bits -- bit 0 alone is shared by Revive/Max Revive/Revival Herb/Sacred
#     Ash *and* Rare Candy; bit 2 redirects Rare Candy's own bit 0 into
#     "level up" instead of "revive", and bit 1 marks Sacred Ash's
#     whole-party revive. `revive` is therefore bit 0 *without* bit 2.
#   hp_restored/pp_restored: bytes @ 29/30 (255 is a "restore to full"
#     sentinel, not a literal HP value).
#   hp_ev_amount .. special_defense_ev_amount: signed bytes @ 23-28, in
#     HP/Attack/Defense/Speed/Sp. Atk/Sp. Def order (the standard internal
#     stat order).
#   friendship_low/medium/high_amount: signed bytes @ 31-33.
# Deliberately not decoded (see plan.md for why): byte 3 (an apparent, only
# partial duplicate of hp_restored); the X-item battle stat-stage encoding
# (bytes 15/17/19/20 -- too few real data points since Gen5 removed X
# Defense/X Sp. Atk entirely); berry growth (the mechanic itself doesn't
# exist in Gen5).
NATURAL_GIFT_TYPE_NONE = 0x1F


def parse_item_record(
    data: bytes,
    *,
    item_id: int,
    data_archive_member: int,
    archive_path: str,
) -> Gen5Item:
    if len(data) != GEN5_ITEM_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen5 item record for item {item_id} must be "
            f"{GEN5_ITEM_RECORD_SIZE} bytes, got {len(data)}"
        )
    price = struct.unpack_from("<H", data, 0)[0] * GEN5_ITEM_PRICE_SCALE
    flags = struct.unpack_from("<H", data, 8)[0]
    party_use = bool(data[12])
    return Gen5Item(
        item_id=item_id,
        data_archive_member=data_archive_member,
        price=price,
        hold_effect_id=data[2],
        pluck_effect_id=data[4],
        fling_effect_id=data[5],
        fling_power=data[6],
        natural_gift_power=data[7],
        natural_gift_type_id=flags & NATURAL_GIFT_TYPE_NONE,
        field_pocket_id=(flags >> 7) & 0xF,
        field_use_function_id=data[10],
        battle_use_function_id=data[11],
        party_use=party_use,
        party_effects=_parse_party_effects(data) if party_use else None,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=data_archive_member
        ),
    )


def _parse_party_effects(data: bytes) -> Gen5ItemPartyEffects:
    status_cures = data[16]
    special_effect = data[17]
    level_up = bool(special_effect & (1 << 2))
    ev_amounts = struct.unpack_from("<6b", data, 23)
    friendship = struct.unpack_from("<3b", data, 31)
    return Gen5ItemPartyEffects(
        heal_sleep=bool(status_cures & (1 << 0)),
        heal_poison=bool(status_cures & (1 << 1)),
        heal_burn=bool(status_cures & (1 << 2)),
        heal_freeze=bool(status_cures & (1 << 3)),
        heal_paralysis=bool(status_cures & (1 << 4)),
        heal_confusion=bool(status_cures & (1 << 5)),
        revive=bool(special_effect & (1 << 0)) and not level_up,
        revive_all=bool(special_effect & (1 << 1)),
        level_up=level_up,
        hp_restored=data[29],
        pp_restored=data[30],
        hp_ev_amount=ev_amounts[0],
        attack_ev_amount=ev_amounts[1],
        defense_ev_amount=ev_amounts[2],
        speed_ev_amount=ev_amounts[3],
        special_attack_ev_amount=ev_amounts[4],
        special_defense_ev_amount=ev_amounts[5],
        friendship_low_amount=friendship[0],
        friendship_medium_amount=friendship[1],
        friendship_high_amount=friendship[2],
    )
