from __future__ import annotations

import struct

from romwiki.engines.gen5.shared.constants import GEN5_BASE_SPECIES_COUNT
from romwiki.schema import (
    RecordProvenance,
    SeasonalEncounterArea,
    SeasonalEncounterMethod,
    SeasonalEncounterSlot,
)
from romwiki.util.errors import InvalidRomError

# Confirmed against the real `a/1/2/6` (WildPokemon) archive: entries are
# either one 232-byte block (no seasonal variation) or four consecutive
# 232-byte blocks (spring/summer/autumn/winter -- Gen5RomHandler.java reads
# these in this order when `useTimeOfDay`), never any other size.
SEASON_BLOCK_SIZE = 232
SEASONS = ("spring", "summer", "autumn", "winter")

# The seven encounter methods, in the ROM's own block order: a 7-byte rate
# header (one byte per method, byte 7 unused/padding) followed by each
# method's slot table back-to-back, sized per `METHOD_SLOT_COUNTS`
# (Gen5Constants.encountersOfEachType, Ajarmar/universal-pokemon-randomizer-zx).
METHOD_NAMES = (
    "grass_cave",
    "doubles_grass",
    "shaking_spots",
    "surfing",
    "surfing_spots",
    "fishing",
    "fishing_spots",
)
METHOD_SLOT_COUNTS = (12, 12, 12, 5, 5, 5, 5)

# Fixed per-slot encounter-chance weights (percent) -- not stored in the ROM,
# only species/levels are. This is the same 12-slot land / 5-slot water
# weighting scheme used since Generation III (Bulbapedia's "Wild Pokémon"
# article), reused here as Gen5Constants.encountersOfEachType's per-method
# slot counts (12 or 5) match those tables exactly.
GRASS_SLOT_CHANCES = (20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1)
WATER_SLOT_CHANCES = (60, 30, 5, 4, 1)
METHOD_SLOT_CHANCES = (
    GRASS_SLOT_CHANCES,
    GRASS_SLOT_CHANCES,
    GRASS_SLOT_CHANCES,
    WATER_SLOT_CHANCES,
    WATER_SLOT_CHANCES,
    WATER_SLOT_CHANCES,
    WATER_SLOT_CHANCES,
)


def parse_encounter_entry(
    data: bytes, *, map_index: int, archive_path: str
) -> tuple[SeasonalEncounterArea, ...]:
    if len(data) == SEASON_BLOCK_SIZE:
        return (
            _parse_block(
                data,
                0,
                map_index=map_index,
                season=None,
                archive_path=archive_path,
            ),
        )
    if len(data) == SEASON_BLOCK_SIZE * 4:
        return tuple(
            _parse_block(
                data,
                index * SEASON_BLOCK_SIZE,
                map_index=map_index,
                season=season,
                archive_path=archive_path,
            )
            for index, season in enumerate(SEASONS)
        )
    raise InvalidRomError(
        f"Gen V encounter entry {map_index} has size {len(data)}, expected "
        f"{SEASON_BLOCK_SIZE} or {SEASON_BLOCK_SIZE * 4}"
    )


def _parse_block(
    data: bytes,
    offset: int,
    *,
    map_index: int,
    season: str | None,
    archive_path: str,
) -> SeasonalEncounterArea:
    methods = {}
    cursor = offset + 8
    for index, (name, count) in enumerate(
        zip(METHOD_NAMES, METHOD_SLOT_COUNTS, strict=True)
    ):
        rate = data[offset + index]
        slots = []
        for slot_index in range(count):
            base = cursor + slot_index * 4
            word = struct.unpack_from("<H", data, base)[0]
            species_id = word & 0x7FF
            form_id = word >> 11
            if rate and not 1 <= species_id <= GEN5_BASE_SPECIES_COUNT:
                raise InvalidRomError(
                    f"Gen V encounter entry {map_index} ({name}) has invalid "
                    f"species ID {species_id}"
                )
            slots.append(
                SeasonalEncounterSlot(
                    species_id=species_id,
                    form_id=form_id,
                    minimum_level=data[base + 2],
                    # Land encounters use one exact level. Their fourth byte
                    # is ignored by the game and may retain stale data after
                    # editing; only water and fishing methods use a range.
                    maximum_level=(data[base + 2] if index < 3 else data[base + 3]),
                )
            )
        methods[name] = SeasonalEncounterMethod(rate=rate, slots=tuple(slots))
        cursor += count * 4
    return SeasonalEncounterArea(
        area_id=map_index,
        map_index=map_index,
        season=season,
        grass_cave=methods["grass_cave"],
        doubles_grass=methods["doubles_grass"],
        shaking_spots=methods["shaking_spots"],
        surfing=methods["surfing"],
        surfing_spots=methods["surfing_spots"],
        fishing=methods["fishing"],
        fishing_spots=methods["fishing_spots"],
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=map_index
        ),
    )
