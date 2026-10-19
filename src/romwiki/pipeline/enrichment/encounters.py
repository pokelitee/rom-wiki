from __future__ import annotations

from typing import Any, cast

from romwiki.engines.concerns import EnrichmentTables
from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment.common import (
    national_dex_id_for_member,
    pokemon_display_name,
)
from romwiki.pipeline.enrichment.names import resolve_item_names, resolve_pokemon_names
from romwiki.pipeline.enrichment.special_encounters import special_encounter_groups
from romwiki.pipeline.semantics.encounter_identity import (
    EncounterSourceType,
    encounter_route_key,
)
from romwiki.schema.enriched import (
    DirectSpecialEncounters,
    EncounterDataset,
    EncounterEnrichedRecord,
    EncounterPokemon,
    ReplacementSlot,
    SlottedSpecialEncounters,
)
from romwiki.schema.versions import ENCOUNTERS_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def enrich_encounter_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    *,
    sprite_version: str | None = None,
) -> EncounterDataset:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Encounter dataset records must be a list")
    adapter = get_engine(dataset["engine"])
    engine = adapter.enrich
    pokemon_names = resolve_pokemon_names(dataset)
    item_names = resolve_item_names(dataset)
    if adapter.formats.encounters == "seasonal":
        enrich_area = enrich_seasonal_encounter_area
    elif adapter.formats.encounters == "method-table":
        enrich_area = enrich_method_table_encounter_area
    else:
        enrich_area = enrich_conditional_encounter_area

    # Conditional sources keep their raw fields, which vary by source type.
    records: list[EncounterEnrichedRecord] = []
    for expected_area, source in enumerate(source_records):
        if source.get("area_id") != expected_area:
            raise DataSourceError("Encounter records must be ordered by area ID")
        if source.get("source_type") == EncounterSourceType.HIDDEN_GROTTO:
            records.append(
                _enrich_hidden_grotto(
                    engine,
                    source,
                    pokedb,
                    sprite_version,
                    pokemon_names,
                    item_names,
                )
            )
        elif source.get("source_type") == EncounterSourceType.DAILY_SWARM:
            pokemon = _encounter_pokemon(
                source["species_id"],
                pokedb,
                sprite_version,
                pokemon_names,
                engine=engine,
            )
            records.append(
                cast(
                    EncounterEnrichedRecord,
                    {
                        **source,
                        "name": source["location"]["name"],
                        "active": True,
                        "pokemon": pokemon,
                    },
                )
            )
        elif source.get("source_type") == EncounterSourceType.HEADBUTT:
            records.append(
                cast(
                    EncounterEnrichedRecord,
                    {
                        **source,
                        "name": source["location"]["name"],
                        "locations": [source["location"]],
                        "active": True,
                        "pools": {
                            kind: [
                                {
                                    **slot,
                                    "pokemon": _encounter_pokemon(
                                        slot["species_id"],
                                        pokedb,
                                        sprite_version,
                                        pokemon_names,
                                        engine=engine,
                                    ),
                                }
                                for slot in slots
                            ]
                            for kind, slots in source["pools"].items()
                        },
                    },
                )
            )
        elif source.get("source_type") == EncounterSourceType.SAFARI_ZONE:
            records.append(
                cast(
                    EncounterEnrichedRecord,
                    {
                        **source,
                        "name": f"Safari Zone — {source['area_name']}",
                        "locations": [],
                        "active": True,
                        "methods": {
                            method_name: {
                                "base_pools": {
                                    time_name: [
                                        {
                                            **slot,
                                            "pokemon": _encounter_pokemon(
                                                slot["species_id"],
                                                pokedb,
                                                sprite_version,
                                                pokemon_names,
                                                engine=engine,
                                            ),
                                        }
                                        for slot in slots
                                    ]
                                    for time_name, slots in method["base_pools"].items()
                                },
                                "block_encounters": [
                                    {
                                        **encounter,
                                        "times": {
                                            time_name: {
                                                **slot,
                                                "pokemon": _encounter_pokemon(
                                                    slot["species_id"],
                                                    pokedb,
                                                    sprite_version,
                                                    pokemon_names,
                                                    engine=engine,
                                                ),
                                            }
                                            for time_name, slot in encounter[
                                                "times"
                                            ].items()
                                        },
                                    }
                                    for encounter in method["block_encounters"]
                                ],
                            }
                            for method_name, method in source["methods"].items()
                        },
                    },
                )
            )
        else:
            records.append(
                enrich_area(engine, source, pokedb, sprite_version, pokemon_names)
            )
    return {
        "schema_version": ENCOUNTERS_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": dataset["engine"],
        "dataset": "wild_encounters",
        "encounter_format": adapter.formats.encounters,
        "record_count": len(records),
        "active_record_count": sum(record["active"] for record in records),
        "source": dataset["source"],
        "records": records,
    }


def enrich_conditional_encounter_area(
    engine: EnrichmentTables,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> EncounterEnrichedRecord:
    if "walking_variants" in source:
        return _enrich_timed_walking_encounter_area(
            engine, source, pokedb, sprite_version, pokemon_names
        )
    walking = {
        "rate": source["walking_rate"],
        "slots": [
            {
                **slot,
                "chance": engine.WALKING_SLOT_CHANCES[index],
                "pokemon": _encounter_pokemon(
                    slot["species_id"],
                    pokedb,
                    sprite_version,
                    pokemon_names,
                    engine=engine,
                ),
            }
            for index, slot in enumerate(source["walking_slots"])
        ],
    }
    methods = {
        name: {
            "rate": method["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"],
                        pokedb,
                        sprite_version,
                        pokemon_names,
                        engine=engine,
                    ),
                }
                for index, slot in enumerate(method["slots"])
            ],
        }
        for name, method, chances in (
            ("surf", source["surf"], engine.WATER_SLOT_CHANCES),
            ("old_rod", source["old_rod"], engine.FISHING_SLOT_CHANCES),
            ("good_rod", source["good_rod"], engine.FISHING_SLOT_CHANCES),
            ("super_rod", source["super_rod"], engine.FISHING_SLOT_CHANCES),
        )
    }
    special: SlottedSpecialEncounters = {
        "swarm": _encounter_special_slots(
            source["swarm_species_ids"],
            source["walking_slots"],
            engine.SWARM_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "day": _encounter_special_slots(
            source["day_species_ids"],
            source["walking_slots"],
            engine.TIMED_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "night": _encounter_special_slots(
            source["night_species_ids"],
            source["walking_slots"],
            engine.TIMED_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "radar": _encounter_pokemon_list(
            source["radar_species_ids"],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "unown_forms": _resolve_unown_forms(engine, source["unown_table_id"]),
        "dual_slot": {
            game: _encounter_special_slots(
                species_ids,
                source["walking_slots"],
                engine.DUAL_SLOT_SLOT_INDICES,
                engine.WALKING_SLOT_CHANCES,
                pokedb,
                sprite_version,
                pokemon_names,
                engine=engine,
            )
            for game, species_ids in source["dual_slot_species_ids"].items()
        },
    }
    active = bool(
        walking["rate"]
        or any(method["rate"] for method in methods.values())
        or any(entry["pokemon"] for entry in special["swarm"])
        or any(entry["pokemon"] for entry in special["day"])
        or any(entry["pokemon"] for entry in special["night"])
        or any(special["radar"])
        or special["unown_forms"]
        or any(
            entry["pokemon"]
            for entries in special["dual_slot"].values()
            for entry in entries
        )
    )
    locations = source.get("locations", [])
    names = list(dict.fromkeys(location["name"] for location in locations))
    return cast(
        EncounterEnrichedRecord,
        {
            "area_id": source["area_id"],
            "name": " / ".join(names) or f"Encounter Area {source['area_id']:03}",
            "locations": locations,
            "active": active,
            "walking": walking,
            **methods,
            "special": special,
            "bonus_slot_methodology_source": engine.BONUS_SLOT_METHODOLOGY_SOURCE,
            "encounter_form_rates": source["encounter_form_rates"],
            "unown_table_id": source["unown_table_id"],
            "provenance": source["provenance"],
        },
    )


def _enrich_timed_walking_encounter_area(
    engine: EnrichmentTables,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None,
    pokemon_names: list[str] | None,
) -> EncounterEnrichedRecord:
    """Enrich a conditional area whose walking slots vary by time of day.

    Its special encounters name species directly instead of replacing walking
    slots, which the `direct-species` marker records.
    """
    walking_variants = {
        period: {
            "rate": source["walking_rate"],
            "slots": [
                {
                    **slot,
                    "chance": engine.WALKING_SLOT_CHANCES[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"],
                        pokedb,
                        sprite_version,
                        pokemon_names,
                        engine=engine,
                    ),
                }
                for index, slot in enumerate(slots)
            ],
        }
        for period, slots in source["walking_variants"].items()
    }
    methods = {
        name: {
            "rate": source[name]["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"],
                        pokedb,
                        sprite_version,
                        pokemon_names,
                        engine=engine,
                    ),
                }
                for index, slot in enumerate(source[name]["slots"])
            ],
        }
        for name, chances in (
            ("surf", engine.WATER_SLOT_CHANCES),
            ("rock_smash", engine.ROCK_SMASH_SLOT_CHANCES),
            ("old_rod", engine.FISHING_SLOT_CHANCES),
            ("good_rod", engine.FISHING_SLOT_CHANCES),
            ("super_rod", engine.FISHING_SLOT_CHANCES),
        )
    }
    special: DirectSpecialEncounters = {
        "format": "direct-species",
        "land_swarm": _encounter_pokemon(
            source["swarm_species_ids"][0],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "surf_swarm": _encounter_pokemon(
            source["swarm_species_ids"][1],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "hoenn_radio": _encounter_pokemon_list(
            source["radio_species_ids"][:2],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "sinnoh_radio": _encounter_pokemon_list(
            source["radio_species_ids"][2:],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "night_fishing": _encounter_pokemon(
            source["night_fishing_species_id"],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
        "fishing_swarm": _encounter_pokemon(
            source["fishing_swarm_species_id"],
            pokedb,
            sprite_version,
            pokemon_names,
            engine=engine,
        ),
    }
    locations = source.get("locations", [])
    names = list(dict.fromkeys(location["name"] for location in locations))
    return cast(
        EncounterEnrichedRecord,
        {
            "area_id": source["area_id"],
            "name": " / ".join(names) or f"Encounter Area {source['area_id']:03}",
            "locations": locations,
            "active": bool(
                source["walking_rate"]
                or any(method["rate"] for method in methods.values())
                or bool(special_encounter_groups(special))
            ),
            "walking": walking_variants["day"],
            "walking_variants": walking_variants,
            **methods,
            "special": special,
            "provenance": source["provenance"],
        },
    )


def enrich_seasonal_encounter_area(
    engine: EnrichmentTables,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> EncounterEnrichedRecord:
    methods = {
        name: {
            "rate": source[name]["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"],
                        pokedb,
                        sprite_version,
                        pokemon_names,
                        form_id=slot.get("form_id", 0),
                        engine=engine,
                    ),
                }
                for index, slot in enumerate(source[name]["slots"])
            ],
        }
        for name, chances in zip(
            engine.ENCOUNTER_METHOD_NAMES,
            engine.ENCOUNTER_METHOD_SLOT_CHANCES,
            strict=True,
        )
    }
    active = any(method["rate"] for method in methods.values())
    location_names = list(dict.fromkeys(source.get("location_names", [])))
    label = f"Map {source['map_index']:03}"
    if source.get("season"):
        label += f" ({source['season'].title()})"
    return cast(
        EncounterEnrichedRecord,
        {
            "area_id": source["area_id"],
            "map_index": source["map_index"],
            "season": source.get("season"),
            "slug": encounter_route_key(source),
            "name": " / ".join(location_names) or label,
            "location_names": location_names,
            "active": active,
            **methods,
            "provenance": source["provenance"],
        },
    )


def enrich_method_table_encounter_area(
    engine: EnrichmentTables,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> EncounterEnrichedRecord:
    """Enrich a Generation III `MethodEncounterArea` record: up to four
    independent methods (land/water/rock-smash/fishing), each an explicit
    min/max level range per slot -- no season system, no swarm/day/night/
    radar/dual-slot/Unown bonus-slot mechanics (see
    `schema/encounters.py::MethodEncounterArea`'s docstring). Reuses the same
    species/level/chance-resolution shape as `enrich_conditional_encounter_area`
    for each present method, without any of that function's Generation
    IV-only bonus-slot handling (there's nothing to enrich there -- this
    engine's raw records never populate those fields at all).
    """
    method_chances = {
        "land": engine.ENCOUNTER_LAND_SLOT_CHANCES,
        "water": engine.ENCOUNTER_WATER_SLOT_CHANCES,
        "rock_smash": engine.ENCOUNTER_ROCK_SMASH_SLOT_CHANCES,
        "fishing": engine.ENCOUNTER_FISHING_SLOT_CHANCES,
    }
    methods = {}
    for name, chances in method_chances.items():
        method = source.get(name)
        if method is None:
            continue
        methods[name] = {
            "rate": method["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"],
                        pokedb,
                        sprite_version,
                        pokemon_names,
                        engine=engine,
                    ),
                }
                for index, slot in enumerate(method["slots"])
            ],
        }
    locations = source.get("locations", [])
    names = list(dict.fromkeys(location["name"] for location in locations))
    return cast(
        EncounterEnrichedRecord,
        {
            "area_id": source["area_id"],
            "name": " / ".join(names) or f"Encounter Area {source['area_id']:03}",
            "locations": locations,
            "active": any(method["rate"] for method in methods.values()),
            **methods,
            "provenance": source["provenance"],
        },
    )


def _enrich_hidden_grotto(
    engine: EnrichmentTables,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None,
    pokemon_names: list[str] | None,
    item_names: list[str] | None,
) -> EncounterEnrichedRecord:
    if item_names is None:
        raise DataSourceError("Hidden Grotto enrichment requires ROM item names")

    def enrich_item(slot: dict[str, Any]) -> dict[str, Any]:
        item_id = slot["item_id"]
        if not 0 < item_id < len(item_names):
            raise DataSourceError(f"Hidden Grotto item ID does not exist: {item_id}")
        name = item_names[item_id]
        return {
            **slot,
            "item": {"id": item_id, "name": name, "slug": pokedb.item_slug(name)},
        }

    pokemon = [
        {
            **slot,
            "pokemon": _encounter_pokemon(
                slot["species_id"],
                pokedb,
                sprite_version,
                pokemon_names,
                form_id=slot["form_id"],
                engine=engine,
            ),
        }
        for slot in source["pokemon"]
    ]
    return cast(
        EncounterEnrichedRecord,
        {
            **source,
            "name": source["location"]["name"],
            "active": True,
            "pokemon": pokemon,
            "visible_items": [enrich_item(slot) for slot in source["visible_items"]],
            "hidden_items": [enrich_item(slot) for slot in source["hidden_items"]],
        },
    )


def _encounter_pokemon_list(
    species_ids: list[int],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
    *,
    engine: EnrichmentTables | None = None,
) -> list[EncounterPokemon | None]:
    return [
        _encounter_pokemon(
            species_id, pokedb, sprite_version, pokemon_names, engine=engine
        )
        for species_id in species_ids
    ]


def _encounter_pokemon(
    species_id: int | None,
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
    *,
    form_id: int = 0,
    engine: EnrichmentTables | None = None,
) -> EncounterPokemon | None:
    if species_id in {None, 0}:
        return None
    form_slug = (
        engine.ENCOUNTER_FORM_SLUGS.get((species_id, form_id))
        if form_id and engine is not None
        else None
    )
    form_label = (
        engine.ENCOUNTER_COSMETIC_FORM_LABELS.get((species_id, form_id))
        if form_id and engine is not None
        else None
    )
    # `id` stays the raw, engine-native species identifier (not the
    # translated National Dex number) -- it's what `ReferenceIndex` keys
    # site-internal Pokémon pages/type lookups by (see
    # `references.py`'s `identity_fields["pokemon"] = "member"`), so
    # translating it here would silently point type badges/links at
    # whichever *other* species happens to share that National Dex number
    # as its own raw member index. Only the PokeDB lookup (a real,
    # universal Pokédex, not this site's own ROM-keyed pages) and the
    # display name need the translated ID.
    national_dex_id = national_dex_id_for_member(engine, species_id)
    reference = (
        pokedb.pokemon_for_name(form_slug)
        if form_slug is not None
        else pokedb.pokemon_for_id(national_dex_id)
    )
    name = (
        title_case_slug(reference["name"])
        if form_slug is not None
        else pokemon_display_name(species_id, reference["name"], pokemon_names)
    )
    if form_label is not None:
        name += f" ({form_label})"
    return {
        "id": species_id,
        "slug": reference["name"],
        "name": name,
        "sprite": pokedb.pokemon_sprite(reference, sprite_version),
    }


def _encounter_special_slots(
    species_ids: tuple[int, ...],
    walking_slots: list[dict[str, Any]],
    slot_indices: tuple[int, ...],
    chances: tuple[int, ...],
    pokedb: PokeDBGeneration,
    sprite_version: str | None,
    pokemon_names: list[str] | None,
    *,
    engine: EnrichmentTables | None = None,
) -> list[ReplacementSlot]:
    """Apply special species replacements without changing slot odds or levels."""
    return [
        {
            "pokemon": _encounter_pokemon(
                species_id, pokedb, sprite_version, pokemon_names, engine=engine
            ),
            "level": walking_slots[slot_index]["level"],
            "chance": chances[slot_index],
        }
        for species_id, slot_index in zip(species_ids, slot_indices, strict=True)
    ]


def _resolve_unown_forms(engine: EnrichmentTables, unown_table_id: int) -> list[str]:
    index = unown_table_id - 1
    if not (0 <= index < len(engine.UNOWN_FORM_TABLES)):
        return []
    return [
        engine.UNOWN_FORM_NAMES[form_id] for form_id in engine.UNOWN_FORM_TABLES[index]
    ]
