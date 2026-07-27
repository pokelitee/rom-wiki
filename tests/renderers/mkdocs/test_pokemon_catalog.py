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
                "obtainability": "wild",
                "wild_obtainable": True,
                "encounter_location_count": 2,
                "minimum_obtainable_level": 5,
            },
        )

    def test_classifies_direct_nonwild_acquisition(self) -> None:
        relationships = _relationships(
            acquisitions=(
                _acquisition("bulbasaur", "static", level=15),
                _acquisition("bulbasaur", "trade", level=None),
            )
        )

        self.assertEqual(
            _catalog_availability("bulbasaur", relationships),
            {
                "obtainability": "static, gift, or trade only",
                "wild_obtainable": False,
                "encounter_location_count": 0,
                "minimum_obtainable_level": 15,
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
