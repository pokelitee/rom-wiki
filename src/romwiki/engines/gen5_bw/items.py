from __future__ import annotations

import struct

from romwiki.schema import Gen5Item, Gen5ItemPartyEffects, RecordProvenance
from romwiki.util.errors import InvalidRomError

GEN5_ITEM_RECORD_SIZE = 36
# Gen5 stores price at 1/10th scale, unlike Gen4 (which stores it directly) --
# verified against Potion=300, Antidote=100, Full Restore=3000, HP Up=9800,
# Iron=9800 (see the byte-layout notes below).
GEN5_ITEM_PRICE_SCALE = 10

# This generation's Bag has only 5 pockets (down from Gen4's 8 -- Poké Balls,
# Battle Items, and Mail were folded into the general "Items" pocket).
# Verified against Bulbapedia's own "List of items by pocket in Pokémon
# Black and White" for a broad real sample: Potion/Antidote/Full Heal/Rare
# Candy/Revive/Full Restore/PP Up/HP Up/Protein all decode to pocket 1
# (Medicine); Master/Ultra/Great/Poké Ball, Escape Rope, Repel, X Attack/
# Speed/Accuracy, Dire Hit, Guard Spec., Leftovers, Black Sludge, Sticky
# Barb, and Choice Band all decode to pocket 0 (Items -- confirming this
# generation really does lump held items, battle consumables, and Balls
# together); TM01 decodes to pocket 2 (TMs & HMs); Oran/Sitrus/Micle Berry
# decode to pocket 3 (Berries); Bicycle/Town Map decode to pocket 4 (Key
# Items).
GEN5_ITEM_POCKET_NAMES = (
    "items",
    "medicine",
    "tm-hm",
    "berries",
    "key-items",
)

# Confirmed byte-identical to Gen4's own field-use function ID enumeration
# (`gen4_dppt.items.GEN4_ITEM_FIELD_USE_NAMES`) for every value checked
# against real ROM data: 1 (healing) for every Medicine-pocket item sampled,
# 2 (town-map) for Town Map, 4 (bicycle) for the Bicycle, 6 (tm-hm) for
# TM01, 8 (berry) for every berry sampled, 21 (escape-rope) for Escape Rope.
# Duplicated here (rather than imported from gen4_dppt) since the two
# engines are independent modules, matching this project's existing
# per-engine constant-table convention. Extended with one new entry (25)
# for the Dowsing MCHN -- this generation's Itemfinder replacement, with no
# Gen4 counterpart -- the only real item in the full 627-item table using a
# function ID past Gen4's original 25-entry enum.
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

# Byte layout confirmed against the real Black ROM's `a/0/2/4` archive (627
# fixed 36-byte records, item ID == archive member index directly -- no ARM9
# item-to-member map exists in Gen5, unlike Gen4). No public documentation or
# decompilation covers this format (Gen4's Item record is backed by the
# `pret/pokeplatinum` decomp; UPR-ZX's Gen5 randomizer config has no item,
# berry, fling, or fossil keys at all). This and an earlier session
# cross-referenced real records against PokeDB's/Bulbapedia's/Serebii's known
# Gen5 item facts to confirm the fields below. The first 12 bytes are
# byte-identical to Gen4's own item record layout; everything from byte 13
# onward diverges, since Gen5 replaced Gen4's one large party-effects
# bitfield with dedicated per-concept byte fields instead:
#   - price: u16 @ 0, x10 (a real Gen5-specific difference -- Gen4 stores
#     price directly). Verified exactly against Potion=300, Antidote=100,
#     Full Restore=3000, HP Up=9800, Iron=9800.
#   - hold_effect_id: byte @ 2. Zero for non-held items, distinct nonzero
#     values per held item, matching Gen4's offset for the same concept.
#   - pluck_effect_id: byte @ 4. Nonzero only for berries.
#   - fling_effect_id: byte @ 5. Nonzero for King's Rock (flinch) and
#     berries (PokeDB reports fling_effect="berry-effect" for both).
#   - fling_power: byte @ 6. Exact matches against PokeDB's known Gen5
#     fling_power values (e.g. Potion=30, Oran Berry=10).
#   - natural_gift_power: byte @ 7. Verified against Oran Berry (60),
#     Sitrus Berry (60), and Micle Berry (80) -- all real, known Gen5
#     Natural Gift power values.
#   - natural_gift_type_id: bits 0-4 of the u16 @ 8. 31 (0x1F) for every
#     non-berry item (a fixed "no type" sentinel); real berries carry a
#     real type ID matching this engine's own `TYPE_NAMES` order --
#     verified against Oran Berry (3, poison), Sitrus Berry (13, psychic),
#     and Micle Berry (5, rock), all matching the well-documented real
#     Generation IV/V Natural Gift type chart.
#   - field_pocket_id: bits 7-10 of the u16 @ 8. See `GEN5_ITEM_POCKET_NAMES`'s
#     own comment for how this was verified.
#   - field_use_function_id: byte @ 10. See `GEN5_ITEM_FIELD_USE_NAMES`'s
#     own comment for how this was verified.
#   - battle_use_function_id: byte @ 11. Distinct nonzero values seen for
#     Poké Balls (1) vs. Medicine-pocket healing items (2); not otherwise
#     named, matching Gen4's own precedent of exposing this as a raw ID.
#   - party_use: bool @ 12. True for every item that targets a specific
#     party member when used (medicine, vitamins, EV-changing berries),
#     false for pure field/key items (Bicycle, Town Map) and items with no
#     use at all (held items, Poké Balls, TMs).
#   - party_effects (only when party_use is true) -- Gen5ItemPartyEffects:
#     - heal_sleep/heal_poison/heal_burn/heal_freeze/heal_paralysis/
#       heal_confusion: individual bits 0-5 of the byte @ 16. Verified
#       against Awakening (bit 0 only), Antidote (bit 1 only), Burn Heal
#       (bit 2), Ice Heal (bit 3), and Full Heal/Full Restore/Lava Cookie/
#       Old Gateau (all 6 bits set, 0x3F) -- exactly the 6 status
#       conditions items can cure in any generation (never infatuation,
#       which matches every real game's own Full Heal/Full Restore text).
#     - revive/revive_all/level_up: bits 0/1/2 of the byte @ 17, a small,
#       fully-disambiguated bitmask (verified exhaustively against all 627
#       items, not just a sample): bit 0 ("this is a special, non-standard
#       party effect") is set for exactly Revive/Max Revive/Revival Herb/
#       Sacred Ash/Rare Candy and nothing else; bit 1 ("...and it affects
#       the whole party") is set for exactly Sacred Ash; bit 2 ("...and it
#       levels the target up instead") is set for exactly Rare Candy. So
#       `revive` is bit 0 *without* bit 2 (Rare Candy also sets bit 0, but
#       means something else entirely once bit 2 redirects it), and
#       `revive_all`/`level_up` are bits 1/2 directly.
#     - hp_restored/pp_restored: bytes @ 29/30. Verified against Potion
#       (20), Super Potion (50), Hyper Potion (200), Full Restore/Max
#       Revive/Revival Herb (255, a "restore to full" sentinel), Energy
#       Root (200), and Elixir (10 PP).
#     - hp_ev_amount .. special_defense_ev_amount: signed bytes @ 23-28,
#       in HP/Attack/Defense/Speed/Sp. Atk/Sp. Def order (the standard
#       internal stat order). Verified against all 6 EV vitamins (HP Up
#       through Carbos, each +10 to exactly its own stat) and all 6
#       EV-reducing berries (Pomeg through Grepa, each -10 to exactly its
#       own stat) -- twelve independent, real, exactly-matching facts.
#     - friendship_low_amount/friendship_medium_amount/
#       friendship_high_amount: signed bytes @ 31-33. Verified against
#       vitamins (+5/+3/+2, a small friendship boost) and the
#       friendship-lowering healing items Heal Powder/Energy Root/Revival
#       Herb (increasingly negative the "harsher" the real item's flavor
#       text describes it as, e.g. Revival Herb's -15/-15/-20 vs. Energy
#       Root's -10/-10/-15) -- matching the well-documented real mechanic
#       where these items heal a lot but sting the Pokémon's mood.
# Deliberately NOT decoded here, since black-box comparison produced no
# single consistent interpretation without a disassembly to check against:
#   - Byte 3 duplicates the HP-restored amount for most (not all) Medicine
#     items; its exact independent purpose (if any) isn't understood.
#   - Battle-only stat-stage changes (X Attack/Speed/Accuracy, Dire Hit,
#     Guard Spec.): bytes 15/17/19/20 clearly encode *something* about
#     which stat and by how much, but Generation V removed X Defense and
#     X Sp. Atk entirely (confirmed absent from the ROM's own item name
#     table), leaving too few real data points to disambiguate a
#     consistent bit-to-stat mapping with confidence.
#   - Berry growth (soft-soil planting time, etc.): Generation V removed
#     the soil-planting mechanic from the base game entirely (berries
#     only come from wild berry trees, NPCs, and the Dream World), so
#     there's no such table to find in the first place.
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
