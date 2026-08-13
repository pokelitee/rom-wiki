from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment_names import (
    reference_name_table,
    resolve_move_names,
    resolve_pokemon_names,
    resolve_type_names,
)
from romwiki.pipeline.enrichment_references import move_name
from romwiki.pipeline.pokemon_enrichment import (
    named_id,
    personal_member_reference,
    replaced_move,
    tutor_location,
    type_id,
    validate_egg_moves,
    validate_machines,
    validate_tutors,
)
from romwiki.schema.versions import MOVES_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def enrich_move_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    machine_dataset: dict[str, Any] | None = None,
    tutor_dataset: dict[str, Any] | None = None,
    egg_move_dataset: dict[str, Any] | None = None,
    *,
    type_names: Mapping[int, str] | None = None,
    move_names: Mapping[int, str] | None = None,
    reference_version: str | None = None,
) -> dict[str, Any]:
    engine = get_engine(dataset["engine"]).enrich
    source_records = dataset.get("records")
    expected_count = engine.MOVE_RECORD_COUNT
    if not isinstance(source_records, list) or len(source_records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} move records")
    rom_move_names = reference_name_table(dataset, "move_names", engine.MOVE_NAME_COUNT)
    type_names = resolve_type_names(engine, dataset, type_names)
    move_names = resolve_move_names(engine, dataset, move_names)
    pokemon_names = resolve_pokemon_names(engine, dataset)

    machines = validate_machines(engine, machine_dataset, dataset["game"])
    machines_by_move: dict[int, list[dict[str, Any]]] = {}
    for machine in machines.values():
        machines_by_move.setdefault(machine["move_id"], []).append(machine)
    tutors, tutor_ids_by_member, tutor_locations = validate_tutors(
        tutor_dataset, dataset["game"]
    )
    members_by_tutor: dict[int, list[int]] = {tutor_id: [] for tutor_id in tutors}
    for member, tutor_ids in tutor_ids_by_member.items():
        for tutor_id in tutor_ids:
            members_by_tutor[tutor_id].append(member)
    tutors_by_move: dict[int, list[dict[str, Any]]] = {}
    for tutor_id, tutor in tutors.items():
        tutors_by_move.setdefault(tutor["move_id"], []).append(
            {
                **tutor,
                "location": tutor_location(tutor, tutor_locations),
                "compatible_pokemon": [
                    personal_member_reference(engine, member, pokedb, pokemon_names)
                    for member in members_by_tutor[tutor_id]
                ],
            }
        )
    egg_moves = validate_egg_moves(engine, egg_move_dataset, dataset["game"])
    egg_move_pokemon: dict[int, list[dict[str, Any]]] = {}
    for species_id, egg_move_set in egg_moves.items():
        pokemon = personal_member_reference(engine, species_id, pokedb, pokemon_names)
        for move_id in set(egg_move_set["move_ids"]):
            egg_move_pokemon.setdefault(move_id, []).append(pokemon)
    records = []
    for expected_id, source in enumerate(source_records):
        if source.get("move_id") != expected_id:
            raise DataSourceError("Move records must be ordered by member ID")
        public = 1 <= expected_id <= engine.MAX_MOVE_ID
        slug = (
            move_name(expected_id, pokedb, move_names)
            if public
            else f"internal-move-{expected_id}"
        )
        records.append(
            {
                **source,
                "slug": slug,
                "name": (
                    rom_move_names[expected_id]
                    if public and rom_move_names is not None
                    else title_case_slug(slug)
                ),
                "replaces": (
                    replaced_move(expected_id, slug, pokedb) if public else None
                ),
                "reference": (
                    pokedb.move_reference(expected_id, reference_version)
                    if public
                    else None
                ),
                "public": public,
                "damage_class": named_id(
                    source["damage_class_id"],
                    engine.DAMAGE_CLASS_NAMES,
                    "move class",
                ),
                "type": type_id(engine, source["type_id"], type_names),
                "machines": machines_by_move.get(expected_id, []),
                "tutors": tutors_by_move.get(expected_id, []),
                "egg_move_pokemon": egg_move_pokemon.get(expected_id, []),
            }
        )
    enriched = {
        "schema_version": MOVES_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": dataset["engine"],
        "dataset": "moves",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": dataset["source"],
        "records": records,
    }
    if machine_dataset is not None:
        enriched["supplemental_sources"] = {"machines": machine_dataset["source"]}
    if tutor_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["move_tutors"] = tutor_dataset[
            "source"
        ]
    if egg_move_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["egg_moves"] = egg_move_dataset[
            "source"
        ]
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    return enriched
