"""Derive renderer-facing cross-dataset relationships once per build.

Split by relationship domain (wild encounters, trainer appearances,
acquisition, move learners, location <-> encounter cross-references) into
sibling modules; this file only orchestrates them and defines the frozen
`RelationshipIndex` result. External code should import from this package
(`romwiki.pipeline.transforms.relationships`), not the `_domain` submodules,
which are this package's private implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from romwiki.pipeline.semantics.encounter_identity import encounter_dataset_format

from ._acquisition import (
    AcquisitionReference,
    _acquisition_references,
    _acquisition_sort_key,
)
from ._learners import MoveLearnerReference, _learner_sort_key, _move_learners
from ._locations import (
    EncounterLocationReference,
    LocationEncounterReference,
    _freeze_encounter_locations,
    _freeze_location_encounters,
    _location_conditional_encounters,
    _location_encounters,
    _safari_zone_headers,
)
from ._shared import (
    _freeze,
    _location_display_name,
    _pokemon_aliases,
    _records,
    _validate_datasets,
)
from ._trainers import TrainerAppearance, _trainer_appearances, _trainer_sort_key
from ._wild import WildEncounterReference, _freeze_wild, _wild_encounters

__all__ = [
    "AcquisitionReference",
    "EncounterLocationReference",
    "LocationEncounterReference",
    "MoveLearnerReference",
    "RelationshipIndex",
    "TrainerAppearance",
    "WildEncounterReference",
    "build_relationship_index",
]


@dataclass(frozen=True, slots=True)
class RelationshipIndex:
    pokemon_wild_encounters: Mapping[str, tuple[WildEncounterReference, ...]]
    pokemon_trainers: Mapping[str, tuple[TrainerAppearance, ...]]
    pokemon_acquisition: Mapping[str, tuple[AcquisitionReference, ...]]
    move_level_up_learners: Mapping[int, tuple[MoveLearnerReference, ...]]
    move_machine_learners: Mapping[int, tuple[MoveLearnerReference, ...]]
    location_encounters: Mapping[int, tuple[LocationEncounterReference, ...]]
    encounter_locations: Mapping[int | str, tuple[EncounterLocationReference, ...]]
    location_labels: Mapping[int, str] = field(default_factory=dict)
    location_conditional_encounters: Mapping[int, tuple[dict[str, Any], ...]] = field(
        default_factory=dict
    )
    location_safari_zone_headers: frozenset[int] = frozenset()


def build_relationship_index(
    datasets: Mapping[str, Mapping[str, Any]],
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

    wild = _wild_encounters(
        encounter_records,
        location_records,
        aliases,
        encounter_dataset_format(datasets.get("encounters")),
    )
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
        location_labels={
            location["header_id"]: _location_display_name(location)
            for location in location_records
        },
        location_conditional_encounters=_location_conditional_encounters(
            encounter_records
        ),
        location_safari_zone_headers=_safari_zone_headers(
            location_records, encounter_records, location_encounters
        ),
    )
