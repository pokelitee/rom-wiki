from __future__ import annotations

import struct

from romwiki.engines.gen3.shared.constants import MACHINE_COUNT, PERSONAL_RECORD_SIZE
from romwiki.engines.gen3.shared.machines import parse_tmhm_learnset
from romwiki.schema import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.util.errors import InvalidRomError

# Field offsets below are Generation III's `struct BaseStats` (pret/
# pokefirered `include/constants/pokemon.h` + `src/data/pokemon/base_stats.h`),
# the same 28-byte layout FireRed, LeafGreen, and Emerald all share:
#   0x00-0x05  base stats (hp, attack, defense, speed, sp. attack, sp. defense)
#   0x06-0x07  type1, type2
#   0x08       catch rate
#   0x09       base experience yield
#   0x0A-0x0B  EV yield bitfield (2 bits each, hp/atk/def/speed/spatk/spdef)
#   0x0C-0x0D  item1 (common wild-held item)
#   0x0E-0x0F  item2 (rare wild-held item)
#   0x10       gender ratio
#   0x11       egg cycles
#   0x12       base friendship
#   0x13       growth rate
#   0x14-0x15  egg group 1, egg group 2
#   0x16-0x17  ability 1, ability 2
#   0x18       safari zone flee rate
#   0x19       bit 0-6 body color, bit 7 no-flip flag
#   0x1A-0x1B  padding
# Unlike Generation IV/V, this struct has no inline TM/HM compatibility
# bitmap -- that's a separate, species-indexed `sTMHMLearnsets` table (see
# `machines.py`'s module comment), passed in here as `tmhm_learnset` since
# the extraction layer owns reading it (same reasoning as
# `resolve_gba_pointer`'s pointer resolution) -- and only two wild-held-item
# slots (no Dark Grass slot, introduced in Generation V) and two ability
# slots (no hidden-ability slot, introduced in Generation V).
#
# The raw item1/item2 values are read but not yet surfaced through
# `wild_held_items` (see below): `pipeline/enrichment/references.py`'s
# `item_reference` resolves a raw item ID straight against PokeDB when no
# ROM-extracted item name table is available, which assumes the ROM's raw
# item ID already matches PokeDB/PokeAPI's numbering. That's true for the
# Nintendo DS engines already onboarded, but hasn't been verified for
# Generation III's own item ordering (e.g. this table's raw common-item
# value for Venomoth decodes to 188, while PokeDB's Silver Powder is 199 --
# they may not be the same numbering at all). Surfacing an unverified
# mapping as fact would violate this repo's evidence-based norm, so this
# stays zeroed -- like `machine_ids`/`machine_masks` above -- until the
# items domain is added with a verified ID mapping (or ROM-extracted item
# names, which sidestep the mapping question entirely).


def parse_personal_record(
    data: bytes,
    *,
    species_id: int,
    archive_path: str,
    tmhm_learnset: bytes = b"",
) -> PokemonPersonalData:
    if len(data) != PERSONAL_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen III personal record {species_id} has size {len(data)}, "
            f"expected {PERSONAL_RECORD_SIZE}"
        )

    if tmhm_learnset:
        bits, machine_masks = parse_tmhm_learnset(tmhm_learnset)
        machine_ids = tuple(
            machine_id
            for machine_id in range(1, MACHINE_COUNT + 1)
            if bits & (1 << (machine_id - 1))
        )
    else:
        machine_ids, machine_masks = (), (0, 0, 0, 0)

    ev_mask = struct.unpack_from("<H", data, 0x0A)[0]
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
        wild_held_items=WildHeldItems(common=0, rare=0),
        gender_ratio=data[0x10],
        hatch_cycles=data[0x11],
        base_friendship=data[0x12],
        growth_rate_id=data[0x13],
        egg_group_ids=(data[0x14], data[0x15]),
        ability_ids=(data[0x16], data[0x17]),
        safari_flee_rate=data[0x18],
        body_color_id=data[0x19] & 0x3F,
        flip_sprite=bool(data[0x19] & 0x40),
        machine_ids=machine_ids,
        machine_masks=machine_masks,
        provenance=RecordProvenance(
            source="rom",
            archive=archive_path,
            member=species_id,
        ),
    )
