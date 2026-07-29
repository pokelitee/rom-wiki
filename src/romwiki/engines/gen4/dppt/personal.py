from __future__ import annotations

import struct

from romwiki.schema import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.util.errors import InvalidRomError

PERSONAL_RECORD_SIZE = 44
GEN4_BASE_SPECIES_COUNT = 493

PERSONAL_FORM_MEMBERS = {
    496: "deoxys-attack",
    497: "deoxys-defense",
    498: "deoxys-speed",
    499: "wormadam-sandy",
    500: "wormadam-trash",
    501: "giratina-origin",
    502: "shaymin-sky",
    503: "rotom-heat",
    504: "rotom-wash",
    505: "rotom-frost",
    506: "rotom-fan",
    507: "rotom-mow",
}

PERSONAL_INTERNAL_MEMBERS = {0: "none", 494: "egg", 495: "bad-egg"}

# Trainer-party form operands that select a battle form with its own
# personal record; slugs match the PERSONAL_FORM_MEMBERS entries above.
TRAINER_FORM_SLUGS = {
    (386, 1): "deoxys-attack",
    (386, 2): "deoxys-defense",
    (386, 3): "deoxys-speed",
    (413, 1): "wormadam-sandy",
    (413, 2): "wormadam-trash",
    (479, 1): "rotom-heat",
    (479, 2): "rotom-wash",
    (479, 3): "rotom-frost",
    (479, 4): "rotom-fan",
    (479, 5): "rotom-mow",
    (487, 1): "giratina-origin",
    (492, 1): "shaymin-sky",
}

# Cosmetic form operands that reuse the base species' personal record but
# change the displayed appearance.
TRAINER_COSMETIC_FORM_LABELS = {
    (412, 1): "Sandy Cloak",
    (412, 2): "Trash Cloak",
    (422, 1): "East Sea",
    (423, 1): "East Sea",
}


def parse_personal_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
) -> PokemonPersonalData:
    if len(data) != PERSONAL_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen IV personal record {species_id} has size {len(data)}, "
            f"expected {PERSONAL_RECORD_SIZE}"
        )

    ev_mask = struct.unpack_from("<H", data, 10)[0]
    padding = struct.unpack_from("<H", data, 26)[0]
    if padding:
        raise InvalidRomError(
            f"Gen IV personal record {species_id} has nonzero padding: {padding}"
        )
    machine_masks = struct.unpack_from("<IIII", data, 28)
    machine_ids = tuple(
        machine_id
        for machine_id in range(1, 129)
        if machine_masks[(machine_id - 1) // 32] & (1 << ((machine_id - 1) % 32))
    )
    return PokemonPersonalData(
        species_id=species_id,
        base_stats=StatBlock(*data[0:6]),
        type_ids=(data[6], data[7]),
        catch_rate=data[8],
        base_experience=data[9],
        ev_yields=StatBlock(
            hp=(ev_mask >> 0) & 0b11,
            attack=(ev_mask >> 2) & 0b11,
            defense=(ev_mask >> 4) & 0b11,
            speed=(ev_mask >> 6) & 0b11,
            special_attack=(ev_mask >> 8) & 0b11,
            special_defense=(ev_mask >> 10) & 0b11,
        ),
        wild_held_items=WildHeldItems(
            common=struct.unpack_from("<H", data, 12)[0],
            rare=struct.unpack_from("<H", data, 14)[0],
        ),
        gender_ratio=data[16],
        hatch_cycles=data[17],
        base_friendship=data[18],
        growth_rate_id=data[19],
        egg_group_ids=(data[20], data[21]),
        ability_ids=(data[22], data[23]),
        safari_flee_rate=data[24],
        body_color_id=data[25] & 0x7F,
        flip_sprite=bool(data[25] & 0x80),
        machine_ids=machine_ids,
        machine_masks=machine_masks,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
