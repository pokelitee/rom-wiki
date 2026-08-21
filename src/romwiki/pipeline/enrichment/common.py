from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def national_dex_id_for_member(engine: Any, member: int) -> int:
    """Translate a raw, engine-native species identifier into its National
    Dex number, wherever the two diverge.

    Every NDS engine's own species numbering already matches the National
    Dex directly, so `engine.INTERNAL_TO_NATIONAL_DEX` is simply absent for
    them (this returns `member` unchanged). Generation III's own internal
    `SPECIES_*` ordering only matches National Dex order through species
    251 (Kanto+Johto); Hoenn-native species (like Kirlia, internal ROM
    index 393) are stored in in-game "regional dex discovery order," not
    National Dex order, requiring the real conversion table
    (`sSpeciesToNationalPokedexNum[]` in the public pokeemerald/pokefirered
    decompilation) `gen3/shared/constants.py` verified this against.
    Verified directly against real ROM data (not just the public source):
    internal index 281 decodes to Combusken's exact real stats on both the
    FireRed and Emerald ROMs, while National Dex #281 is Kirlia -- the two
    numbering schemes are genuinely different starting at species 252.
    """
    return getattr(engine, "INTERNAL_TO_NATIONAL_DEX", {}).get(member, member)


def pokemon_display_name(
    species_id: int, slug: str, pokemon_names: list[str] | None
) -> str:
    if pokemon_names is not None and 0 < species_id < len(pokemon_names):
        return pokemon_names[species_id]
    return title_case_slug(slug)


def validate_egg_moves(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Egg move dataset must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Egg move records must be a list")
    # Two provenance shapes coexist here: a sparse ARM9-overlay table (Gen IV,
    # one entry per species that actually has egg moves, ordered by
    # table_index) and a dense per-species NARC archive (Gen V, one member per
    # species -- including ones with zero egg moves -- carrying a shared
    # RecordProvenance instead).
    if records and "provenance" in records[0]:
        return _validate_dense_egg_moves(engine, records)
    return _validate_sparse_egg_moves(engine, records)


def _validate_dense_egg_moves(
    engine: Any, records: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    result = {}
    for expected_member, record in enumerate(records):
        species_id = record.get("species_id")
        move_ids = record.get("move_ids")
        if species_id != expected_member:
            raise DataSourceError("Egg move records must be ordered by member ID")
        if not isinstance(move_ids, (list, tuple)) or any(
            not isinstance(move_id, int) or not 1 <= move_id <= engine.MAX_MOVE_ID
            for move_id in move_ids
        ):
            raise DataSourceError("Egg move record contains invalid move IDs")
        # Unlike the sparse (Gen IV) table, this generation's real ROM data
        # does contain a handful of duplicate move IDs within one species'
        # record (e.g. Swinub's own table lists Mud Shot twice) -- rejecting
        # them would mean guessing at "corrected" data instead of decoding
        # what's actually there; _enrich_egg_moves dedupes for display.
        if move_ids:
            result[species_id] = record
    return result


def _validate_sparse_egg_moves(
    engine: Any, records: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    result = {}
    previous_species = 0
    for expected_index, record in enumerate(records):
        species_id = record.get("species_id")
        move_ids = record.get("move_ids")
        if (
            not isinstance(species_id, int)
            or not previous_species < species_id <= engine.BASE_SPECIES_COUNT
            or record.get("table_index") != expected_index
        ):
            raise DataSourceError("Egg move records must be ordered by species ID")
        if (
            not isinstance(move_ids, (list, tuple))
            or not move_ids
            or any(
                not isinstance(move_id, int) or not 1 <= move_id <= engine.MAX_MOVE_ID
                for move_id in move_ids
            )
        ):
            raise DataSourceError("Egg move record contains invalid move IDs")
        if len(move_ids) != len(set(move_ids)) and not getattr(
            engine, "ALLOW_DUPLICATE_EGG_MOVES", False
        ):
            raise DataSourceError("Egg move record contains duplicate move IDs")
        result[species_id] = record
        previous_species = species_id
    return result


def validate_machines(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Machine dataset must be for the same game")
    records = dataset.get("records")
    expected_count = engine.MACHINE_COUNT
    if not isinstance(records, list) or len(records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} machine records")
    result = {}
    for expected_id, record in enumerate(records, start=1):
        if record.get("machine_id") != expected_id:
            raise DataSourceError("Machine records must be ordered by machine ID")
        result[expected_id] = record
    return result


def validate_tutors(
    dataset: dict[str, Any] | None, game: str
) -> tuple[dict[int, dict[str, Any]], dict[int, list[int]], list[str]]:
    if dataset is None:
        return {}, {}, []
    if dataset.get("game") != game:
        raise DataSourceError("Tutor dataset must be for the same game")
    records = dataset.get("records")
    special_records = dataset.get("special_records", [])
    compatibility = dataset.get("compatibility")
    special_compatibility = dataset.get("special_compatibility", [])
    location_names = dataset.get("location_names")
    if not isinstance(records, list) or not records:
        raise DataSourceError("Tutor records must be a nonempty list")
    if not isinstance(special_records, list):
        raise DataSourceError("Special tutor records must be a list")
    if not isinstance(compatibility, list):
        raise DataSourceError("Tutor compatibility records must be a list")
    if not isinstance(special_compatibility, list):
        raise DataSourceError("Special tutor compatibility records must be a list")
    if not isinstance(location_names, list) or not all(
        isinstance(name, str) for name in location_names
    ):
        raise DataSourceError("Tutor location names must be a list")
    tutors = {}
    for expected_id, record in enumerate(records + special_records, start=1):
        if record.get("tutor_id") != expected_id:
            raise DataSourceError("Tutor records must be ordered by tutor ID")
        if record.get("kind") == "special":
            if not isinstance(record.get("location_name"), str):
                raise DataSourceError("Special tutor has an invalid location")
        else:
            location_id = record.get("location_id")
            if not isinstance(location_id, int) or not 0 <= location_id < len(
                location_names
            ):
                raise DataSourceError("Tutor record references an unknown location")
        tutors[expected_id] = record
    ids_by_member: dict[int, list[int]] = {}
    for compatibility_group in (compatibility, special_compatibility):
        group_members = set()
        for record in compatibility_group:
            member = record.get("personal_member")
            tutor_ids = record.get("tutor_ids")
            if not isinstance(member, int) or member in group_members:
                raise DataSourceError(
                    "Tutor compatibility has an invalid personal member"
                )
            group_members.add(member)
            if not isinstance(tutor_ids, (list, tuple)) or any(
                value not in tutors for value in tutor_ids
            ):
                raise DataSourceError(
                    "Tutor compatibility references an unknown tutor ID"
                )
            existing = ids_by_member.setdefault(member, [])
            if any(value in existing for value in tutor_ids):
                raise DataSourceError(
                    "Tutor compatibility contains duplicate tutor IDs"
                )
            existing.extend(tutor_ids)
    return tutors, ids_by_member, location_names


def tutor_location(tutor: dict[str, Any], location_names: list[str]) -> dict[str, Any]:
    if tutor.get("kind") == "special":
        return {"id": None, "name": tutor["location_name"]}
    location_id = tutor["location_id"]
    return {"id": location_id, "name": location_names[location_id]}


def personal_member_reference(
    engine: Any,
    member: int,
    pokedb: PokeDBGeneration,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any]:
    if member in engine.FORM_MEMBERS:
        slug = engine.FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        national_dex_id = pokedb.pokemon_for_species(reference["species"])["id"]
        name = title_case_slug(slug)
    elif 1 <= member <= engine.BASE_SPECIES_COUNT:
        national_dex_id = national_dex_id_for_member(engine, member)
        reference = pokedb.pokemon_for_id(national_dex_id)
        slug = reference["name"]
        # `pokemon_names` (when present) is a ROM-extracted name table
        # indexed the same raw way as `member` itself, not National Dex
        # order -- must use `member` here, not `national_dex_id`.
        name = pokemon_display_name(member, slug, pokemon_names)
    else:
        raise DataSourceError(
            f"Tutor compatibility references internal member {member}"
        )
    return {
        "member": member,
        "national_dex_id": national_dex_id,
        "slug": slug,
        "name": name,
    }


def named_id(value: int, names: tuple[str, ...], label: str) -> dict[str, Any]:
    if not 0 <= value < len(names):
        raise DataSourceError(f"Unknown {label} ID: {value}")
    return {"id": value, "name": names[value]}


def replaced_move(
    move_id: int, slug: str, pokedb: PokeDBGeneration
) -> dict[str, Any] | None:
    canonical_slug = pokedb.move_name(move_id)
    if canonical_slug is None or canonical_slug == slug:
        return None
    return {"slug": canonical_slug, "name": title_case_slug(canonical_slug)}


def type_id(
    engine: Any, value: int, type_names: Mapping[int, str] | None
) -> dict[str, Any]:
    if type_names is not None and value in type_names:
        return {"id": value, "name": type_names[value]}
    return named_id(value, engine.TYPE_NAMES, "type")
