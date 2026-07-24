from __future__ import annotations

import struct

from romwiki.schema import Gen5Item, RecordProvenance
from romwiki.util.errors import InvalidRomError

GEN5_ITEM_RECORD_SIZE = 36

# Byte layout confirmed against the real Black ROM's `a/0/2/4` archive (627
# fixed 36-byte records, item ID == archive member index directly -- no ARM9
# item-to-member map exists in Gen5, unlike Gen4). No public documentation or
# decompilation covers this format (Gen4's Item record is backed by the
# `pret/pokeplatinum` decomp; UPR-ZX's Gen5 randomizer config has no item,
# berry, fling, or fossil keys at all). This session cross-referenced ~567 of
# 627 real records against PokeDB's Gen5 item data (cost, fling_power,
# fling_effect) to confirm the fields below:
#   - price: u16 @ 0, x10 (a real Gen5-specific difference -- Gen4 stores
#     price directly). Verified exactly against Potion=300, Antidote=100,
#     Full Restore=3000, HP Up=9800, Iron=9800.
#   - hold_effect_id: byte @ 2. Zero for non-held items, distinct nonzero
#     values per held item, matching Gen4's offset for the same concept.
#   - pluck_effect_id: byte @ 4. Nonzero only for the two sampled berries.
#   - fling_effect_id: byte @ 5. Nonzero for King's Rock (flinch) and both
#     sampled berries (PokeDB reports fling_effect="berry-effect" for both).
#   - fling_power: byte @ 6. 299/301 exact matches against PokeDB's known
#     Gen5 fling_power values.
# Deliberately NOT decoded here, since black-box comparison produced no
# single consistent interpretation without a disassembly to check against:
#   - Byte 3 fits Black Sludge/Sticky Barb/Micle Berry's HP-fraction
#     denominator exactly (16/8/4), but contradicts on Leftovers (10, not
#     16) -- no clean single meaning found.
#   - natural_gift_power (decodable at byte 7) is meaningless without a
#     Natural Gift type, and Gen5 has no `type_names_member` configured for
#     items.
#   - Pocket ID, field/battle-use function IDs, `party_use`/`party_effects`
#     (Gen4's full 43-field block), berries (no separate berry archive
#     found), and fossil revival (no ARM9 table found) are entirely
#     unlocated. A future slice should start from this comment rather than
#     re-deriving the confirmed fields above from scratch.


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
    price = struct.unpack_from("<H", data, 0)[0] * 10
    return Gen5Item(
        item_id=item_id,
        data_archive_member=data_archive_member,
        price=price,
        hold_effect_id=data[2],
        pluck_effect_id=data[4],
        fling_effect_id=data[5],
        fling_power=data[6],
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=data_archive_member
        ),
    )
