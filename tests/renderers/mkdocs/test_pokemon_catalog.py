from __future__ import annotations

import unittest

from romwiki.pipeline.relationships import (
    AcquisitionReference,
    RelationshipIndex,
    WildEncounterReference,
)
from romwiki.renderers.mkdocs.pokemon import _catalog_availability


class PokemonCatalogAvailabilityTests(unittest.TestCase):
    def test_summarizes_wild_locations_and_minimum_known_level(self) -> None:
        relationships = _relationships(
            wild=(
                WildEncounterReference(
                    pokemon_slug="bulbasaur",
                    area_id=1,
                    area_name="Route 1",
                    encounter_route_key=1,
                    method="walking",
                    minimum_level=5,
                    maximum_level=7,
                    chance=20,
                    condition=None,
                    season=None,
                    locations=((10, "Route 1"), (11, "Route 1 Gate")),
                    versions=(),
                ),
            ),
            acquisitions=(
                _acquisition("bulbasaur", "gift", level=10),
            ),
        )

        self.assertEqual(
            _catalog_availability("bulbasaur", relationships),
            {
                "availability_methods": ["wild", "gift"],
                "wild_location_count": 2,
            },
        )

    def test_preserves_each_direct_nonwild_acquisition_method(self) -> None:
        relationships = _relationships(
            acquisitions=(
                _acquisition("bulbasaur", "static", level=15),
                _acquisition("bulbasaur", "trade", level=None),
                _acquisition("bulbasaur", "honey-tree", level=None),
            )
        )

        self.assertEqual(
            _catalog_availability("bulbasaur", relationships),
            {
                "availability_methods": ["static", "trade", "honey-tree"],
                "wild_location_count": 0,
            },
        )

    def test_marks_records_without_a_direct_source_explicitly(self) -> None:
        self.assertEqual(
            _catalog_availability("bulbasaur", _relationships()),
            {
                "availability_methods": ["no-known-direct-source"],
                "wild_location_count": 0,
            },
        )


def _relationships(
    *,
    wild: tuple[WildEncounterReference, ...] = (),
    acquisitions: tuple[AcquisitionReference, ...] = (),
) -> RelationshipIndex:
    return RelationshipIndex(
        pokemon_wild_encounters={"bulbasaur": wild} if wild else {},
        pokemon_trainers={},
        pokemon_acquisition={"bulbasaur": acquisitions} if acquisitions else {},
        move_level_up_learners={},
        move_machine_learners={},
        location_encounters={},
    )


def _acquisition(
    pokemon_slug: str, kind: str, *, level: int | None
) -> AcquisitionReference:
    return AcquisitionReference(
        pokemon_slug=pokemon_slug,
        kind=kind,
        location_id=None,
        location_name=None,
        level=level,
        detail=None,
        source_item_id=None,
        source_item_slug=None,
        versions=(),
    )
