from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from romwiki.pipeline.encounter_identity import encounter_route_key
from romwiki.util.errors import DataSourceError


@dataclass(frozen=True, slots=True)
class WildEncounterReference:
    pokemon_slug: str
    area_id: int
    area_name: str
    encounter_route_key: int | str
    method: str
    minimum_level: int | None
    maximum_level: int | None
    chance: int | float | None
    condition: str | None
    season: str | None
    locations: tuple[tuple[int | None, str], ...]
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrainerAppearance:
    pokemon_slug: str
    trainer_id: int
    trainer_name: str
    class_name: str
    party_position: int
    level: int
    held_item_id: int | None
    held_item_name: str | None
    held_item_slug: str | None
    locations: tuple[tuple[int | None, str], ...]
    linked: bool
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcquisitionReference:
    pokemon_slug: str
    kind: str
    location_id: int | None
    location_name: str | None
    level: int | None
    detail: str | None
    source_item_id: int | None
    source_item_slug: str | None
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MoveLearnerReference:
    move_id: int
    pokemon_id: int | str
    pokemon_name: str
    pokemon_slug: str
    pokemon_form: str | None
    method: str
    level: int | None
    machine_id: int | None
    machine_name: str | None
    machine_kind: str | None
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocationEncounterReference:
    header_id: int
    area_id: int
    map_index: int
    season: str | None
    encounter_route_key: int | str
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EncounterLocationReference:
    encounter_route_key: int | str
    header_id: int
    location_name: str
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RelationshipIndex:
    pokemon_wild_encounters: Mapping[str, tuple[WildEncounterReference, ...]]
    pokemon_trainers: Mapping[str, tuple[TrainerAppearance, ...]]
    pokemon_acquisition: Mapping[str, tuple[AcquisitionReference, ...]]
    move_level_up_learners: Mapping[int, tuple[MoveLearnerReference, ...]]
    move_machine_learners: Mapping[int, tuple[MoveLearnerReference, ...]]
    location_encounters: Mapping[int, tuple[LocationEncounterReference, ...]]
    encounter_locations: Mapping[
        int | str, tuple[EncounterLocationReference, ...]
    ]


def build_relationship_index(
    datasets: Mapping[str, dict[str, Any]],
) -> RelationshipIndex:
    """Derive renderer-facing cross-dataset relationships once per build."""
    _validate_datasets(datasets)
    pokemon_records = _records(datasets, "pokemon")
    encounter_records = _records(datasets, "encounters")
    trainer_records = _records(datasets, "trainers")
    location_records = _records(datasets, "locations")
    item_records = _records(datasets, "items")
    trade_records = _records(datasets, "trades")
    aliases = _pokemon_aliases(pokemon_records)

    wild = _wild_encounters(encounter_records, location_records, aliases)
    trainers = _trainer_appearances(trainer_records, aliases)
    acquisition = _acquisition_references(
        pokemon_records,
        location_records,
        item_records,
        trade_records,
        aliases,
    )
    level_up, machines = _move_learners(pokemon_records)
    location_encounters = _freeze_location_encounters(
        _location_encounters(
            location_records,
            encounter_records,
            require_matches="locations" in datasets and "encounters" in datasets,
        )
    )
    encounter_locations = _freeze_encounter_locations(
        location_records,
        location_encounters,
    )
    return RelationshipIndex(
        pokemon_wild_encounters=_freeze_wild(wild),
        pokemon_trainers=_freeze(trainers, _trainer_sort_key),
        pokemon_acquisition=_freeze(acquisition, _acquisition_sort_key),
        move_level_up_learners=_freeze(level_up, _learner_sort_key),
        move_machine_learners=_freeze(machines, _learner_sort_key),
        location_encounters=location_encounters,
        encounter_locations=encounter_locations,
    )


def _validate_datasets(datasets: Mapping[str, dict[str, Any]]) -> None:
    games = {
        str(dataset["game"])
        for dataset in datasets.values()
        if dataset is not None
        and dataset.get("records") is not None
        and dataset.get("game") is not None
    }
    if len(games) > 1:
        raise DataSourceError("Relationship datasets must be for the same game")


def _records(datasets: Mapping[str, dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    dataset = datasets.get(kind)
    if dataset is None:
        return []
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError(f"{kind} dataset records must be a list")
    return records


def _pokemon_aliases(
    records: list[dict[str, Any]],
) -> dict[int | str, str]:
    aliases: dict[int | str, str] = {}
    ambiguous: set[int | str] = set()
    for record in records:
        if not record.get("public", True):
            continue
        slug = record.get("slug")
        if not isinstance(slug, str):
            continue
        for alias in (
            slug,
            record.get("member"),
            record.get("national_dex_id"),
        ):
            if alias is None or alias in ambiguous:
                continue
            existing = aliases.get(alias)
            if existing is not None and existing != slug:
                aliases.pop(alias)
                ambiguous.add(alias)
            else:
                aliases[alias] = slug
    return aliases


def _pokemon_slug(
    value: Mapping[str, Any] | None,
    species_id: int | None,
    aliases: Mapping[int | str, str],
) -> str | None:
    if value is not None:
        slug = value.get("slug")
        if isinstance(slug, str) and slug in aliases:
            return aliases[slug]
    return aliases.get(species_id) if species_id is not None else None


def _record_versions(record: Mapping[str, Any]) -> tuple[str, ...]:
    versions = record.get("versions")
    if isinstance(versions, list) and all(isinstance(value, str) for value in versions):
        return tuple(versions)
    return ()


def _record_variants(
    record: dict[str, Any],
) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    variants = record.get("version_variants")
    if isinstance(variants, dict):
        for version, variant in variants.items():
            if isinstance(version, str) and isinstance(variant, dict):
                yield (version,), variant
        return
    yield _record_versions(record), record


_ENCOUNTER_METHODS = (
    ("walking", "Walking"),
    ("surf", "Surf"),
    ("rock_smash", "Rock Smash"),
    ("old_rod", "Old Rod"),
    ("good_rod", "Good Rod"),
    ("super_rod", "Super Rod"),
    ("grass_cave", "Grass / cave"),
    ("doubles_grass", "Doubles grass"),
    ("shaking_spots", "Shaking spots"),
    ("surfing", "Surfing"),
    ("surfing_spots", "Surfing spots"),
    ("fishing", "Fishing"),
    ("fishing_spots", "Fishing spots"),
)


def _wild_encounters(
    records: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[WildEncounterReference]]:
    result: dict[str, list[WildEncounterReference]] = defaultdict(list)
    location_index = _encounter_location_index(locations)
    for merged_record in records:
        for versions, record in _record_variants(merged_record):
            common = {
                "area_id": record["area_id"],
                "area_name": record["name"],
                "encounter_route_key": encounter_route_key(record),
                "season": record.get("season"),
                "locations": _encounter_locations(record, location_index),
                "versions": versions,
            }
            for key, label in _ENCOUNTER_METHODS:
                if key == "walking" and record.get("walking_variants"):
                    continue
                method = record.get(key)
                if not isinstance(method, dict) or not method.get("rate"):
                    continue
                for slot in method.get("slots", []):
                    _add_wild_reference(result, aliases, slot, label, None, common)
            _add_conditional_special_encounters(result, aliases, record, common)
    return result


def _add_conditional_special_encounters(
    result: dict[str, list[WildEncounterReference]],
    aliases: Mapping[int | str, str],
    record: Mapping[str, Any],
    common: dict[str, Any],
) -> None:
    special = record.get("special")
    if not isinstance(special, dict):
        return
    for period, method in record.get("walking_variants", {}).items():
        for slot in method.get("slots", []):
            _add_wild_reference(result, aliases, slot, "Walking", period, common)
    if special.get("format") == "hgss":
        for key, condition in (
            ("land_swarm", "land swarm"),
            ("surf_swarm", "surf swarm"),
            ("hoenn_radio", "Hoenn Sound radio"),
            ("sinnoh_radio", "Sinnoh Sound radio"),
            ("night_fishing", "night fishing"),
            ("fishing_swarm", "fishing swarm"),
        ):
            values = special.get(key, [])
            if isinstance(values, dict) or values is None:
                values = [values]
            for pokemon in values:
                _add_wild_reference(
                    result,
                    aliases,
                    {"pokemon": pokemon, "species_id": (pokemon or {}).get("id")},
                    (
                        "Fishing"
                        if "fishing" in condition
                        else "Surf"
                        if condition == "surf swarm"
                        else "Walking"
                    ),
                    condition,
                    common,
                )
        return
    for key, label in (
        ("swarm", "Walking"),
        ("day", "Walking"),
        ("night", "Walking"),
    ):
        for slot in special.get(key, []):
            _add_wild_reference(result, aliases, slot, label, key, common)
    for game, slots in special.get("dual_slot", {}).items():
        for slot in slots:
            _add_wild_reference(
                result, aliases, slot, "Walking", f"dual-slot: {game}", common
            )
    for pokemon in special.get("radar", []):
        _add_wild_reference(
            result,
            aliases,
            {"pokemon": pokemon, "species_id": (pokemon or {}).get("id")},
            "Walking",
            "Poké Radar",
            common,
        )


def _add_wild_reference(
    result: dict[str, list[WildEncounterReference]],
    aliases: Mapping[int | str, str],
    slot: Mapping[str, Any],
    method: str,
    condition: str | None,
    common: Mapping[str, Any],
) -> None:
    pokemon = slot.get("pokemon")
    slug = _pokemon_slug(
        pokemon if isinstance(pokemon, Mapping) else None,
        slot.get("species_id"),
        aliases,
    )
    if slug is None:
        return
    level = slot.get("level")
    minimum = slot.get("minimum_level", level)
    maximum = slot.get("maximum_level", level)
    result[slug].append(
        WildEncounterReference(
            pokemon_slug=slug,
            method=method,
            minimum_level=minimum if isinstance(minimum, int) else None,
            maximum_level=maximum if isinstance(maximum, int) else None,
            chance=slot.get("chance"),
            condition=condition,
            **common,
        )
    )


def _encounter_locations(
    record: Mapping[str, Any],
    location_index: Mapping[tuple[str, int], tuple[tuple[int, str], ...]],
) -> tuple[tuple[int | None, str], ...]:
    values: list[tuple[int | None, str]] = []
    locations = record.get("locations")
    if isinstance(locations, list):
        values.extend(
            (location.get("header_id"), location["name"])
            for location in locations
            if isinstance(location, dict) and isinstance(location.get("name"), str)
        )
    lookup_key = (
        ("map-index", record["map_index"])
        if isinstance(record.get("map_index"), int)
        else ("area-id", record["area_id"])
    )
    values.extend(location_index.get(lookup_key, ()))
    if not values:
        names = record.get("location_names")
        if isinstance(names, list):
            values.extend((None, name) for name in names if isinstance(name, str))
    return tuple(dict.fromkeys(values))


def _encounter_location_index(
    records: list[dict[str, Any]],
) -> dict[tuple[str, int], tuple[tuple[int, str], ...]]:
    values: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)
    for record in records:
        if isinstance(record.get("encounter_id"), int):
            values[("area-id", record["encounter_id"])].append(
                (record["header_id"], record["name"])
            )
        if isinstance(record.get("encounter_map_index"), int):
            values[("map-index", record["encounter_map_index"])].append(
                (record["header_id"], record["name"])
            )
    return {key: tuple(dict.fromkeys(locations)) for key, locations in values.items()}


def _trainer_appearances(
    records: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[TrainerAppearance]]:
    result: dict[str, list[TrainerAppearance]] = defaultdict(list)
    for record in records:
        versions = _record_versions(record)
        locations = _trainer_locations(record)
        for position, member in enumerate(record.get("party", []), start=1):
            pokemon = member.get("pokemon")
            slug = _pokemon_slug(
                pokemon if isinstance(pokemon, Mapping) else None,
                member.get("species_id"),
                aliases,
            )
            if slug is None:
                continue
            held_item = member.get("held_item")
            held_item = held_item if isinstance(held_item, dict) else {}
            result[slug].append(
                TrainerAppearance(
                    pokemon_slug=slug,
                    trainer_id=record["trainer_id"],
                    trainer_name=record["name"],
                    class_name=record["class_name"],
                    party_position=position,
                    level=member["level"],
                    held_item_id=held_item.get("id"),
                    held_item_name=held_item.get("name"),
                    held_item_slug=held_item.get("slug"),
                    locations=locations,
                    linked=bool(locations),
                    versions=versions,
                )
            )
    return result


def _trainer_locations(
    record: Mapping[str, Any],
) -> tuple[tuple[int | None, str], ...]:
    values = []
    seen = set()
    for key in ("locations", "script_references"):
        for location in record.get(key, []):
            identity = (location.get("header_id"), location.get("name"))
            if isinstance(identity[1], str) and identity not in seen:
                seen.add(identity)
                values.append(identity)
    return tuple(values)


def _acquisition_references(
    pokemon_records: list[dict[str, Any]],
    location_records: list[dict[str, Any]],
    item_records: list[dict[str, Any]],
    trade_records: list[dict[str, Any]],
    aliases: Mapping[int | str, str],
) -> dict[str, list[AcquisitionReference]]:
    result: dict[str, list[AcquisitionReference]] = defaultdict(list)
    for location in location_records:
        versions = _record_versions(location)
        common = {
            "location_id": location["header_id"],
            "location_name": location["name"],
            "versions": versions,
        }
        for gift in location.get("pokemon_gifts", []):
            gift_kind = "egg" if gift.get("kind") == "egg" else "gift"
            _add_acquisition(result, aliases, gift, gift_kind, common)
        for encounter in location.get("static_encounters", []):
            _add_acquisition(result, aliases, encounter, "static", common)
        for trade in location.get("npc_trades", []):
            offered = {
                "species_id": trade.get("offered_species_id"),
                "level": None,
                "detail": f"Trade for {trade.get('requested_species_name', 'Pokémon')}",
            }
            _add_acquisition(
                result,
                aliases,
                offered,
                "trade",
                {
                    **common,
                    "versions": tuple(trade.get("versions", versions)),
                },
            )
        honey_tree = location.get("honey_tree")
        if isinstance(honey_tree, dict):
            for rarity in ("common", "uncommon", "rare"):
                for pokemon in honey_tree.get(rarity, []):
                    _add_acquisition(
                        result,
                        aliases,
                        pokemon,
                        "honey-tree",
                        {**common, "detail": rarity},
                    )
        daily = location.get("daily_encounter_pool")
        if isinstance(daily, dict):
            for pokemon in daily.get("species", []):
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    daily["kind"],
                    common,
                )
            for pokemon in daily.get("pre_national_dex_species") or []:
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    daily["kind"],
                    {**common, "detail": "before National Pokédex"},
                )

    for item in item_records:
        pokemon = item.get("revives_into")
        if isinstance(pokemon, dict):
            locations = item.get("revives_at") or [None]
            for location in locations:
                _add_acquisition(
                    result,
                    aliases,
                    pokemon,
                    "fossil-revival",
                    {
                        "location_id": (
                            location.get("header_id") if location else None
                        ),
                        "location_name": location.get("name") if location else None,
                        "detail": item.get("name"),
                        "source_item_id": item.get("item_id"),
                        "source_item_slug": item.get("slug"),
                        "versions": _record_versions(item),
                    },
                )

    for trade in trade_records:
        offered = trade.get("offered_pokemon")
        requested = trade.get("requested_pokemon") or {}
        if not isinstance(offered, dict):
            continue
        if trade.get("locations"):
            # Fixed trades were already emitted from the location records,
            # which preserve nested sibling-version ownership precisely.
            continue
        _add_acquisition(
            result,
            aliases,
            {
                "pokemon": offered,
                "species_id": offered.get("species_id"),
                "detail": _detached_trade_detail(trade, requested),
            },
            "trade",
            {
                "location_id": None,
                "location_name": None,
                "versions": _record_versions(trade),
            },
        )

    # Preserve static encounters that have no resolved location record.
    for pokemon in pokemon_records:
        slug = pokemon.get("slug")
        if not isinstance(slug, str):
            continue
        versions = _record_versions(pokemon)
        for encounter in pokemon.get("static_encounters", []):
            location = encounter.get("location") or {}
            result[slug].append(
                AcquisitionReference(
                    pokemon_slug=slug,
                    kind="egg" if encounter.get("is_egg") else "static",
                    location_id=location.get("header_id"),
                    location_name=location.get("name"),
                    level=None if encounter.get("is_egg") else encounter.get("level"),
                    detail=encounter.get("command"),
                    source_item_id=None,
                    source_item_slug=None,
                    versions=versions,
                )
            )
    return result


def _detached_trade_detail(
    trade: dict[str, Any], requested: dict[str, Any]
) -> str:
    requested_name = requested.get("name")
    if trade.get("interaction") == "xtransceiver":
        ot_name = trade.get("ot_name")
        label = (
            f"Xtransceiver trade with {ot_name}"
            if ot_name
            else "Xtransceiver trade"
        )
    else:
        label = "Trade"
    return f"{label} for {requested_name}" if requested_name else label


def _add_acquisition(
    result: dict[str, list[AcquisitionReference]],
    aliases: Mapping[int | str, str],
    value: Mapping[str, Any],
    kind: str,
    common: Mapping[str, Any],
) -> None:
    slug = _pokemon_slug(
        value.get("pokemon") if isinstance(value.get("pokemon"), Mapping) else value,
        value.get("species_id"),
        aliases,
    )
    if slug is None:
        return
    result[slug].append(
        AcquisitionReference(
            pokemon_slug=slug,
            kind=kind,
            location_id=common.get("location_id"),
            location_name=common.get("location_name"),
            level=value.get("level"),
            detail=value.get(
                "detail",
                value.get("command", common.get("detail")),
            ),
            source_item_id=common.get("source_item_id"),
            source_item_slug=common.get("source_item_slug"),
            versions=tuple(common.get("versions", ())),
        )
    )


def _move_learners(
    pokemon_records: list[dict[str, Any]],
) -> tuple[
    dict[int, list[MoveLearnerReference]],
    dict[int, list[MoveLearnerReference]],
]:
    level_up: dict[int, list[MoveLearnerReference]] = defaultdict(list)
    machines: dict[int, list[MoveLearnerReference]] = defaultdict(list)
    for pokemon in pokemon_records:
        if not pokemon.get("public", True) or not isinstance(pokemon.get("slug"), str):
            continue
        versions = _record_versions(pokemon)
        slug = pokemon["slug"]
        pokemon_id = pokemon.get("member", slug)
        pokemon_name = str(pokemon.get("name", slug))
        pokemon_form = pokemon.get("form")
        for entry in pokemon.get("level_up_moves", []):
            move = entry.get("move")
            if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                continue
            level_up[move["id"]].append(
                MoveLearnerReference(
                    move_id=move["id"],
                    pokemon_id=pokemon_id,
                    pokemon_name=pokemon_name,
                    pokemon_slug=slug,
                    pokemon_form=pokemon_form,
                    method="level-up",
                    level=entry.get("level"),
                    machine_id=None,
                    machine_name=None,
                    machine_kind=None,
                    versions=versions,
                )
            )
        for machine in pokemon.get("machines", []):
            move = machine.get("move")
            if not isinstance(move, dict) or not isinstance(move.get("id"), int):
                continue
            machines[move["id"]].append(
                MoveLearnerReference(
                    move_id=move["id"],
                    pokemon_id=pokemon_id,
                    pokemon_name=pokemon_name,
                    pokemon_slug=slug,
                    pokemon_form=pokemon_form,
                    method="machine",
                    level=None,
                    machine_id=machine.get("id"),
                    machine_name=machine.get("name"),
                    machine_kind=machine.get("kind"),
                    versions=versions,
                )
            )
    return level_up, machines


def _location_encounters(
    locations: list[dict[str, Any]],
    encounters: list[dict[str, Any]],
    *,
    require_matches: bool,
) -> dict[int, list[LocationEncounterReference]]:
    by_map_index: dict[int, list[tuple[tuple[str, ...], dict[str, Any]]]] = defaultdict(
        list
    )
    for merged_record in encounters:
        for versions, record in _record_variants(merged_record):
            map_index = record.get("map_index", record.get("area_id"))
            if isinstance(map_index, int):
                by_map_index[map_index].append((versions, record))

    result: dict[int, list[LocationEncounterReference]] = defaultdict(list)
    unmatched = []
    for location in locations:
        map_index = location.get("encounter_map_index")
        if not isinstance(map_index, int):
            continue
        matching_encounters = by_map_index.get(map_index, [])
        if require_matches and not matching_encounters:
            unmatched.append((location["header_id"], map_index))
            continue
        location_versions = _record_versions(location)
        for encounter_versions, encounter in matching_encounters:
            result[location["header_id"]].append(
                LocationEncounterReference(
                    header_id=location["header_id"],
                    area_id=encounter["area_id"],
                    map_index=map_index,
                    season=encounter.get("season"),
                    encounter_route_key=encounter_route_key(encounter),
                    versions=encounter_versions or location_versions,
                )
            )
    if unmatched:
        examples = ", ".join(
            f"header {header_id} -> map {map_index}"
            for header_id, map_index in unmatched[:10]
        )
        suffix = f" (and {len(unmatched) - 10} more)" if len(unmatched) > 10 else ""
        raise DataSourceError(
            "Location wild-encounter references have no matching encounter "
            f"records: {examples}{suffix}"
        )
    return result


def _freeze(
    values: Mapping[Any, list[Any]],
    sort_key: Any,
) -> dict[Any, tuple[Any, ...]]:
    return {
        key: tuple(_deduplicate(sorted(entries, key=sort_key)))
        for key, entries in sorted(values.items(), key=lambda item: item[0])
    }


def _freeze_wild(
    values: Mapping[str, list[WildEncounterReference]],
) -> dict[str, tuple[WildEncounterReference, ...]]:
    result = {}
    for slug, entries in sorted(values.items()):
        grouped: dict[tuple[Any, ...], WildEncounterReference] = {}
        for entry in entries:
            key = (
                entry.pokemon_slug,
                entry.area_id,
                entry.area_name,
                entry.encounter_route_key,
                entry.method,
                entry.minimum_level,
                entry.maximum_level,
                entry.condition,
                entry.season,
                entry.locations,
                entry.versions,
            )
            existing = grouped.get(key)
            if existing is None or existing.chance is None or entry.chance is None:
                grouped.setdefault(key, entry)
                continue
            grouped[key] = WildEncounterReference(
                pokemon_slug=entry.pokemon_slug,
                area_id=entry.area_id,
                area_name=entry.area_name,
                encounter_route_key=entry.encounter_route_key,
                method=entry.method,
                minimum_level=entry.minimum_level,
                maximum_level=entry.maximum_level,
                chance=existing.chance + entry.chance,
                condition=entry.condition,
                season=entry.season,
                locations=entry.locations,
                versions=entry.versions,
            )
        result[slug] = tuple(sorted(grouped.values(), key=_wild_sort_key))
    return result


def _freeze_location_encounters(
    values: Mapping[int, list[LocationEncounterReference]],
) -> dict[int, tuple[LocationEncounterReference, ...]]:
    result = {}
    for header_id, entries in sorted(values.items()):
        grouped: dict[tuple[int, int, str | None, int | str], set[str]] = defaultdict(
            set
        )
        for entry in entries:
            grouped[
                (
                    entry.area_id,
                    entry.map_index,
                    entry.season,
                    entry.encounter_route_key,
                )
            ].update(entry.versions)
        result[header_id] = tuple(
            sorted(
                (
                    LocationEncounterReference(
                        header_id=header_id,
                        area_id=area_id,
                        map_index=map_index,
                        season=season,
                        encounter_route_key=route_key,
                        versions=tuple(sorted(versions)),
                    )
                    for (
                        area_id,
                        map_index,
                        season,
                        route_key,
                    ), versions in grouped.items()
                ),
                key=_location_sort_key,
            )
        )
    return result


def _freeze_encounter_locations(
    locations: list[dict[str, Any]],
    location_encounters: Mapping[int, tuple[LocationEncounterReference, ...]],
) -> dict[int | str, tuple[EncounterLocationReference, ...]]:
    location_names = {
        location["header_id"]: location["name"]
        for location in locations
    }
    values: dict[int | str, list[EncounterLocationReference]] = defaultdict(list)
    for header_id, encounters in location_encounters.items():
        location_name = location_names[header_id]
        for encounter in encounters:
            values[encounter.encounter_route_key].append(
                EncounterLocationReference(
                    encounter_route_key=encounter.encounter_route_key,
                    header_id=header_id,
                    location_name=location_name,
                    versions=encounter.versions,
                )
            )

    result = {}
    for route_key, entries in sorted(values.items(), key=lambda item: str(item[0])):
        grouped: dict[tuple[int, str], set[str]] = defaultdict(set)
        for entry in entries:
            grouped[(entry.header_id, entry.location_name)].update(entry.versions)
        result[route_key] = tuple(
            EncounterLocationReference(
                encounter_route_key=route_key,
                header_id=header_id,
                location_name=location_name,
                versions=tuple(sorted(versions)),
            )
            for (header_id, location_name), versions in sorted(
                grouped.items(), key=lambda item: (item[0][1], item[0][0])
            )
        )
    return result


def _deduplicate(values: Iterable[Any]) -> Iterable[Any]:
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        yield value


def _wild_sort_key(value: WildEncounterReference) -> tuple[Any, ...]:
    return (
        value.area_name,
        value.area_id,
        value.season or "",
        value.method,
        value.condition or "",
        value.minimum_level if value.minimum_level is not None else -1,
        value.maximum_level if value.maximum_level is not None else -1,
        value.chance if value.chance is not None else -1,
        value.versions,
    )


def _trainer_sort_key(value: TrainerAppearance) -> tuple[Any, ...]:
    return value.trainer_id, value.party_position, value.versions


def _acquisition_sort_key(value: AcquisitionReference) -> tuple[Any, ...]:
    return (
        value.kind,
        value.location_name or "",
        value.location_id if value.location_id is not None else -1,
        value.level if value.level is not None else -1,
        value.detail or "",
        value.source_item_id if value.source_item_id is not None else -1,
        value.versions,
    )


def _learner_sort_key(value: MoveLearnerReference) -> tuple[Any, ...]:
    return (
        value.pokemon_slug,
        value.level if value.level is not None else -1,
        value.machine_id if value.machine_id is not None else -1,
        value.versions,
    )


def _location_sort_key(value: LocationEncounterReference) -> tuple[Any, ...]:
    return value.area_id, value.season or "", value.versions
