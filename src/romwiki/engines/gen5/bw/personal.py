from __future__ import annotations

import struct

from romwiki.schema import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.util.errors import InvalidRomError

from .constants import (
    GEN5_MACHINE_COUNT,
    PERSONAL_PLACEHOLDER_MEMBER,
    PERSONAL_PLACEHOLDER_RECORD_SIZE,
    PERSONAL_RECORD_SIZE,
)

# Field offsets below are PersonalInfo5BW's (PKHeX.Core/PersonalInfo/Info/
# PersonalInfo5BW.cs), confirmed against a real Black ROM record (species 1,
# Bulbasaur): stats/types/catch rate, all three ability slots (overgrow/none/
# chlorophyll), EV yield (1 special attack), gender ratio, hatch cycles, base
# friendship, growth rate, egg groups, base experience (64), and the TM/HM
# bitmap's Grass Pledge bit all decode to Bulbasaur's known real values.
#
# Gen5 adds a third wild-held-item slot (Dark Grass, at 0x10). Verified
# against real Black ROM records: Sawk holds Black Belt normally but a
# distinct Expert Belt in Dark Grass (a well-documented, memorable Gen5
# fact), confirming this offset rather than some unrelated field.


def parse_personal_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> PokemonPersonalData:
    if (
        species_id == PERSONAL_PLACEHOLDER_MEMBER
        and len(data) == PERSONAL_PLACEHOLDER_RECORD_SIZE
    ):
        data = data + bytes(PERSONAL_RECORD_SIZE - len(data))
    if len(data) != PERSONAL_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V personal record {species_id} has size {len(data)}, "
            f"expected {PERSONAL_RECORD_SIZE}"
        )

    ev_mask = struct.unpack_from("<H", data, 0x0A)[0]
    tmhm_bits = int.from_bytes(data[0x28:0x35], "little")
    machine_masks = tuple((tmhm_bits >> (32 * word)) & 0xFFFFFFFF for word in range(4))
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
        egg_group_ids=(data[0x16], data[0x17]),
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
