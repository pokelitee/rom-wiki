from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from romwiki.schema import Gen5StaticEncounter, RecordProvenance


def parse_static_encounters(
    read_script_member: Callable[[int], bytes],
    entries: Sequence[Mapping[str, Any]],
    *,
    egg_indices: frozenset[int],
    archive_path: str,
) -> tuple[Gen5StaticEncounter, ...]:
    """Decode gift/single-Pokémon encounters placed by field scripts.

    Unlike the wild-encounter table (`gen5_bw/encounters.py`), these aren't a
    single contiguous table -- each encounter is a species ID (and, unless
    it's an egg, a level) patched into one specific script file at a literal
    byte offset. `entries` comes from `gen5_offsets.ini`'s `StaticPokemon{}`
    facts (see plan.md for the source and verification). Each fact lists
    every script file/offset pair the species ID is duplicated at; only the
    first pair is read here, matching `Gen5RomHandler.getPokemon()`.
    """
    encounters = []
    for encounter_id, entry in enumerate(entries):
        species_file, species_offset = entry["species"]
        species_id = _read_word(read_script_member(species_file), species_offset)
        level_entry = entry.get("level")
        level = None
        if level_entry is not None:
            level_file, level_offset = level_entry
            level = read_script_member(level_file)[level_offset]
        encounters.append(
            Gen5StaticEncounter(
                encounter_id=encounter_id,
                species_id=species_id,
                level=level,
                is_egg=encounter_id in egg_indices,
                provenance=RecordProvenance(
                    source="rom", archive=archive_path, member=encounter_id
                ),
            )
        )
    return tuple(encounters)


def _read_word(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)
