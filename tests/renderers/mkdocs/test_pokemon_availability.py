from __future__ import annotations

import unittest

from romwiki.pipeline.relationships import (
    AcquisitionReference,
    WildEncounterReference,
)
from romwiki.renderers.mkdocs.pokemon import _append_availability


class PokemonAvailabilityTests(unittest.TestCase):
    def test_renders_wild_encounters_with_links_conditions_and_versions(self) -> None:
        lines: list[str] = []
        _append_availability(
            lines,
            (
                WildEncounterReference(
                    pokemon_slug="basculin-blue-striped",
                    area_id=8,
                    area_name="Route 1",
                    method="Fishing",
                    minimum_level=35,
                    maximum_level=55,
                    chance=60,
                    condition=None,
                    season="spring",
                    locations=((6, "Route 1"),),
                    versions=("white",),
                ),
            ),
            (),
            "pokemon/basculin-blue-striped.md",
        )

        page = "\n".join(lines)
        self.assertIn("### Wild encounters", page)
        self.assertIn("[Route 1](../encounters/area-008.md)", page)
        self.assertIn("[Route 1](../locations/header-006.md)", page)
        self.assertIn("| Fishing | 35–55 | 60% | Spring | White |", page)

    def test_groups_supported_acquisition_sources_and_links_fossil_items(
        self,
    ) -> None:
        lines: list[str] = []
        _append_availability(
            lines,
            (),
            (
                _acquisition("static", level=20, detail="WildBattle"),
                _acquisition("egg", level=None, detail=None),
                _acquisition(
                    "fossil-revival",
                    location_id=None,
                    location_name=None,
                    detail="Root Fossil",
                    source_item_id=99,
                    source_item_slug="root-fossil",
                ),
            ),
            "pokemon/lileep.md",
        )

        page = "\n".join(lines)
        self.assertIn("### Static encounters", page)
        self.assertIn("### Gift eggs", page)
        self.assertIn("### Fossil revival", page)
        self.assertIn("[Oreburgh City](../locations/header-001.md)", page)
        self.assertIn("[Root Fossil](../items/root-fossil.md)", page)
        self.assertNotIn("## Static encounters", page.splitlines())

    def test_renders_one_concise_empty_state(self) -> None:
        lines: list[str] = []

        _append_availability(lines, (), (), "pokemon/bulbasaur.md")

        self.assertEqual(lines, ["No acquisition source is available.", ""])


def _acquisition(
    kind: str,
    *,
    location_id: int | None = 1,
    location_name: str | None = "Oreburgh City",
    level: int | None = None,
    detail: str | None = None,
    source_item_id: int | None = None,
    source_item_slug: str | None = None,
) -> AcquisitionReference:
    return AcquisitionReference(
        pokemon_slug="lileep",
        kind=kind,
        location_id=location_id,
        location_name=location_name,
        level=level,
        detail=detail,
        source_item_id=source_item_id,
        source_item_slug=source_item_slug,
        versions=(),
    )


if __name__ == "__main__":
    unittest.main()
