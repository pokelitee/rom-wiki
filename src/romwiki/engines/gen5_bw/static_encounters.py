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
    byte offset. `entries` comes from Ajarmar/universal-pokemon-randomizer-zx's
    `gen5_offsets.ini` (`StaticPokemon{}` facts, `[Black (U)]`/`[White (U)]`
    sections -- identical between Black/White, since White's own section just
    copies Black's `StaticPokemon{}` list rather than redefining it). Each
    fact lists every script file/offset pair the species ID is duplicated at
    (one per place the same event can trigger from); only the first pair is
    read here, matching `Gen5RomHandler.getPokemon()`'s own behavior.

    Verified against 12 real Black ROM entries spanning every present-in-BW1
    category this covers: starter-choice monkeys (Pansage/Pansear/Panpour,
    level 10), the free tutorial Magikarp (level 5), event legendaries
    (Reshiram/Zekrom level 50, the trio Cobalion/Terrakion/Virizion level 42,
    Landorus level 70, Kyurem level 75), and fossil revivals (Cranidos/
    Shieldon level 25) -- all real, correct, level-appropriate facts.
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
