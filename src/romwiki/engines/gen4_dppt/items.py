from __future__ import annotations

import struct

from romwiki.schema import Gen4Item, ItemPartyEffects, RecordProvenance
from romwiki.util.errors import InvalidRomError

GEN4_ITEM_RECORD_SIZE = 34
GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE = 8
GEN4_ITEM_POCKET_NAMES = (
    "items",
    "medicine",
    "poke-balls",
    "tm-hm",
    "berries",
    "mail",
    "battle-items",
    "key-items",
)
GEN4_ITEM_FIELD_USE_NAMES = (
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
)


def parse_item_record(
    data: bytes, *, item_id: int, data_archive_member: int, archive_path: str
) -> Gen4Item:
    if len(data) != GEN4_ITEM_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV item record must be {GEN4_ITEM_RECORD_SIZE} bytes, got {len(data)}"
        )
    price = struct.unpack_from("<H", data)[0]
    flags = struct.unpack_from("<H", data, 8)[0]
    party_flags = int.from_bytes(data[14:21], "little")
    signed_values = struct.unpack_from("<6b", data, 21)
    friendship = struct.unpack_from("<3b", data, 29)
    party_effects = ItemPartyEffects(
        heal_sleep=bool(party_flags & (1 << 0)),
        heal_poison=bool(party_flags & (1 << 1)),
        heal_burn=bool(party_flags & (1 << 2)),
        heal_freeze=bool(party_flags & (1 << 3)),
        heal_paralysis=bool(party_flags & (1 << 4)),
        heal_confusion=bool(party_flags & (1 << 5)),
        heal_attract=bool(party_flags & (1 << 6)),
        guard_spec=bool(party_flags & (1 << 7)),
        revive=bool(party_flags & (1 << 8)),
        revive_all=bool(party_flags & (1 << 9)),
        level_up=bool(party_flags & (1 << 10)),
        evolve=bool(party_flags & (1 << 11)),
        attack_stages=(party_flags >> 12) & 0xF,
        defense_stages=(party_flags >> 16) & 0xF,
        special_attack_stages=(party_flags >> 20) & 0xF,
        special_defense_stages=(party_flags >> 24) & 0xF,
        speed_stages=(party_flags >> 28) & 0xF,
        accuracy_stages=(party_flags >> 32) & 0xF,
        critical_hit_stages=(party_flags >> 36) & 0x3,
        pp_up=bool(party_flags & (1 << 38)),
        pp_max=bool(party_flags & (1 << 39)),
        pp_restore=bool(party_flags & (1 << 40)),
        pp_restore_all=bool(party_flags & (1 << 41)),
        hp_restore=bool(party_flags & (1 << 42)),
        hp_ev=bool(party_flags & (1 << 43)),
        attack_ev=bool(party_flags & (1 << 44)),
        defense_ev=bool(party_flags & (1 << 45)),
        speed_ev=bool(party_flags & (1 << 46)),
        special_attack_ev=bool(party_flags & (1 << 47)),
        special_defense_ev=bool(party_flags & (1 << 48)),
        friendship_low=bool(party_flags & (1 << 49)),
        friendship_medium=bool(party_flags & (1 << 50)),
        friendship_high=bool(party_flags & (1 << 51)),
        hp_ev_amount=signed_values[0],
        attack_ev_amount=signed_values[1],
        defense_ev_amount=signed_values[2],
        speed_ev_amount=signed_values[3],
        special_attack_ev_amount=signed_values[4],
        special_defense_ev_amount=signed_values[5],
        hp_restored=data[27],
        pp_restored=data[28],
        friendship_low_amount=friendship[0],
        friendship_medium_amount=friendship[1],
        friendship_high_amount=friendship[2],
    )
    return Gen4Item(
        item_id=item_id,
        data_archive_member=data_archive_member,
        price=price,
        hold_effect_id=data[2],
        hold_effect_parameter=data[3],
        pluck_effect_id=data[4],
        fling_effect_id=data[5],
        fling_power=data[6],
        natural_gift_power=data[7],
        natural_gift_type_id=flags & 0x1F,
        prevent_toss=bool(flags & (1 << 5)),
        selectable=bool(flags & (1 << 6)),
        field_pocket_id=(flags >> 7) & 0xF,
        battle_pocket_mask=(flags >> 11) & 0x1F,
        field_use_function_id=data[10],
        battle_use_function_id=data[11],
        party_use=bool(data[12]),
        party_effects=party_effects,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=data_archive_member
        ),
    )


def find_item_archive_members(
    arm9_data: bytes, *, item_count: int, data_member_count: int
) -> tuple[int, tuple[int, ...]]:
    table_size = item_count * GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE
    candidates = []
    identity_prefix = min(item_count, 64)
    for offset in range(0, len(arm9_data) - table_size + 1, 2):
        if any(
            struct.unpack_from(
                "<H", arm9_data, offset + item_id * GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE
            )[0]
            != item_id
            for item_id in range(identity_prefix)
        ):
            continue
        member_ids = tuple(
            struct.unpack_from(
                "<H", arm9_data, offset + item_id * GEN4_ITEM_ARCHIVE_MAP_RECORD_SIZE
            )[0]
            for item_id in range(item_count)
        )
        if any(member_id >= data_member_count for member_id in member_ids):
            continue
        if set(member_ids) != set(range(data_member_count)):
            continue
        candidates.append((offset, member_ids))
    if len(candidates) != 1:
        raise InvalidRomError(
            f"Expected one Gen IV item archive map, found {len(candidates)}"
        )
    return candidates[0]
