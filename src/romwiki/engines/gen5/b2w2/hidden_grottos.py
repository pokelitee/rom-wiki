from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.schema import RecordProvenance
from romwiki.util.errors import InvalidRomError

HIDDEN_GROTTO_RECORD_SIZE = 220
HIDDEN_GROTTO_POKEMON_GROUP_SIZE = 26
HIDDEN_GROTTO_GROUP_COUNT = 4
HIDDEN_GROTTO_VERSION_GROUP_COUNT = 3
HIDDEN_GROTTO_ITEM_OFFSET = 156

_POKEMON_POOL_CHANCES = (1, 4, 15)
_ITEM_POOL_CHANCES = (1, 4, 10, 25)


@dataclass(frozen=True, slots=True)
class HiddenGrottoPokemonSlot:
    species_id: int
    form_id: int
    minimum_level: int
    maximum_level: int
    female_percentage: int
    pool_chance: int
    group: int


@dataclass(frozen=True, slots=True)
class HiddenGrottoItemSlot:
    item_id: int
    pool_chance: int
    group: int


@dataclass(frozen=True, slots=True)
class HiddenGrotto:
    grotto_id: int
    pokemon: tuple[HiddenGrottoPokemonSlot, ...]
    visible_items: tuple[HiddenGrottoItemSlot, ...]
    hidden_items: tuple[HiddenGrottoItemSlot, ...]
    provenance: RecordProvenance


def parse_hidden_grotto_record(
    data: bytes,
    *,
    grotto_id: int,
    archive_path: str,
    version_group: int,
    species_count: int,
    item_count: int,
    valid_forms: frozenset[tuple[int, int]],
) -> HiddenGrotto:
    if len(data) != HIDDEN_GROTTO_RECORD_SIZE:
        raise InvalidRomError(
            f"Hidden Grotto member {grotto_id} has size {len(data)}, expected "
            f"{HIDDEN_GROTTO_RECORD_SIZE}"
        )
    if version_group not in {0, 1}:
        raise InvalidRomError(f"Invalid Hidden Grotto version group {version_group}")

    pokemon = []
    group_base = version_group * HIDDEN_GROTTO_VERSION_GROUP_COUNT
    for pool_index, pool_chance in enumerate(_POKEMON_POOL_CHANCES):
        offset = (group_base + pool_index) * HIDDEN_GROTTO_POKEMON_GROUP_SIZE
        species_ids = struct.unpack_from("<4H", data, offset)
        maximum_levels = data[offset + 8 : offset + 12]
        minimum_levels = data[offset + 12 : offset + 16]
        female_percentages = data[offset + 16 : offset + 20]
        form_ids = data[offset + 20 : offset + 24]
        padding = data[offset + 24 : offset + 26]
        if padding != b"\0\0":
            raise InvalidRomError(
                f"Hidden Grotto member {grotto_id} group {pool_index} has "
                "nonzero padding"
            )
        for group in range(HIDDEN_GROTTO_GROUP_COUNT):
            species_id = species_ids[group]
            form_id = form_ids[group]
            minimum_level = minimum_levels[group]
            maximum_level = maximum_levels[group]
            female_percentage = female_percentages[group]
            if not 0 < species_id < species_count:
                raise InvalidRomError(
                    f"Hidden Grotto member {grotto_id} references invalid species "
                    f"{species_id}"
                )
            if not 0 < minimum_level <= maximum_level <= 100:
                raise InvalidRomError(
                    f"Hidden Grotto member {grotto_id} has invalid level range "
                    f"{minimum_level}-{maximum_level}"
                )
            if female_percentage > 100:
                raise InvalidRomError(
                    f"Hidden Grotto member {grotto_id} has invalid female percentage "
                    f"{female_percentage}"
                )
            if form_id and (species_id, form_id) not in valid_forms:
                raise InvalidRomError(
                    f"Hidden Grotto member {grotto_id} references invalid form "
                    f"{species_id}:{form_id}"
                )
            pokemon.append(
                HiddenGrottoPokemonSlot(
                    species_id=species_id,
                    form_id=form_id,
                    minimum_level=minimum_level,
                    maximum_level=maximum_level,
                    female_percentage=female_percentage,
                    pool_chance=pool_chance,
                    group=group,
                )
            )

    item_groups = struct.unpack_from("<32H", data, HIDDEN_GROTTO_ITEM_OFFSET)
    visible_items = _parse_item_slots(
        item_groups[:16], grotto_id=grotto_id, item_count=item_count
    )
    hidden_items = _parse_item_slots(
        item_groups[16:], grotto_id=grotto_id, item_count=item_count
    )
    return HiddenGrotto(
        grotto_id=grotto_id,
        pokemon=tuple(pokemon),
        visible_items=visible_items,
        hidden_items=hidden_items,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=grotto_id
        ),
    )


def hidden_grotto_id_for_dispatch(
    script_used: int, *, dispatch_base: int, grotto_count: int
) -> int | None:
    grotto_id = script_used - dispatch_base
    return grotto_id if 0 <= grotto_id < grotto_count else None


def _parse_item_slots(
    item_ids: tuple[int, ...], *, grotto_id: int, item_count: int
) -> tuple[HiddenGrottoItemSlot, ...]:
    slots = []
    for pool_index, pool_chance in enumerate(_ITEM_POOL_CHANCES):
        for group in range(HIDDEN_GROTTO_GROUP_COUNT):
            item_id = item_ids[pool_index * HIDDEN_GROTTO_GROUP_COUNT + group]
            if not 0 < item_id < item_count:
                raise InvalidRomError(
                    f"Hidden Grotto member {grotto_id} references invalid item "
                    f"{item_id}"
                )
            slots.append(
                HiddenGrottoItemSlot(
                    item_id=item_id, pool_chance=pool_chance, group=group
                )
            )
    return tuple(slots)


__all__ = [
    "HIDDEN_GROTTO_RECORD_SIZE",
    "HiddenGrotto",
    "HiddenGrottoItemSlot",
    "HiddenGrottoPokemonSlot",
    "hidden_grotto_id_for_dispatch",
    "parse_hidden_grotto_record",
]
