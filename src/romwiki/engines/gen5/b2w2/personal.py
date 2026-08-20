from __future__ import annotations

import struct

from romwiki.schema import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.util.errors import InvalidRomError

from .constants import GEN5_MACHINE_COUNT, PERSONAL_RECORD_SIZE


def parse_personal_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
    repair_invalid_secondary_egg_group: bool = False,
) -> PokemonPersonalData:
    """Decode one 76-byte PersonalInfo5B2W2 record.

    The first 60 bytes retain BW's layout. B2W2 appends 16 bytes of shard-tutor
    compatibility; that compatibility is consumed by the tutor dataset rather
    than duplicated in the normalized personal record.
    """
    if len(data) != PERSONAL_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V B2W2 personal record {species_id} has size {len(data)}, "
            f"expected {PERSONAL_RECORD_SIZE}"
        )

    ev_mask = struct.unpack_from("<H", data, 0x0A)[0]
    egg_group_ids = (data[0x16], data[0x17])
    if (
        repair_invalid_secondary_egg_group
        and egg_group_ids[0] < 16
        and egg_group_ids[1] >= 16
    ):
        egg_group_ids = (egg_group_ids[0], egg_group_ids[0])
    tmhm_bits = int.from_bytes(data[0x28:0x35], "little")
    machine_masks: tuple[int, int, int, int] = (
        (tmhm_bits >> 0) & 0xFFFFFFFF,
        (tmhm_bits >> 32) & 0xFFFFFFFF,
        (tmhm_bits >> 64) & 0xFFFFFFFF,
        (tmhm_bits >> 96) & 0xFFFFFFFF,
    )
    machine_ids = tuple(
        machine_id
        for machine_id in range(1, GEN5_MACHINE_COUNT + 1)
        if machine_masks[(machine_id - 1) // 32] & (1 << ((machine_id - 1) % 32))
    )
    return PokemonPersonalData(
        species_id=species_id,
        base_stats=StatBlock(*data[0:6]),
        type_ids=(data[6], data[7]),
        catch_rate=data[8],
        base_experience=struct.unpack_from("<H", data, 0x22)[0],
        ev_yields=StatBlock(
            hp=(ev_mask >> 0) & 0b11,
            attack=(ev_mask >> 2) & 0b11,
            defense=(ev_mask >> 4) & 0b11,
            speed=(ev_mask >> 6) & 0b11,
            special_attack=(ev_mask >> 8) & 0b11,
            special_defense=(ev_mask >> 10) & 0b11,
        ),
        wild_held_items=WildHeldItems(
            common=struct.unpack_from("<H", data, 0x0C)[0],
            rare=struct.unpack_from("<H", data, 0x0E)[0],
            dark_grass=struct.unpack_from("<H", data, 0x10)[0],
        ),
        gender_ratio=data[0x12],
        hatch_cycles=data[0x13],
        base_friendship=data[0x14],
        growth_rate_id=data[0x15],
        egg_group_ids=egg_group_ids,
        ability_ids=(data[0x18], data[0x19], data[0x1A]),
        safari_flee_rate=data[0x1B],
        body_color_id=data[0x21] & 0x3F,
        flip_sprite=bool(data[0x21] & 0x40),
        machine_ids=machine_ids,
        machine_masks=machine_masks,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
