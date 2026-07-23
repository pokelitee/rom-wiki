"""Proves the enrichment and rendering layers hold no gen4_dppt-specific
branches: a second, fake engine registered only for this test must flow
through unmodified, exactly as a real second engine eventually would.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import types
import unittest

from romwiki.engines.gen4_dppt import parse_encounter_record
from romwiki.engines.registry import EngineAdapter, get_engine, _ENGINES
from romwiki.pipeline.enrich import enrich_encounter_dataset, enrich_personal_dataset
from romwiki.renderers.mkdocs import render_encounter_pages, render_pokemon_pages
from romwiki.sources import PokeDBGeneration
from tests.test_enrichment import _source_record


_FAKE_ENGINE_ID = "fake_test_engine"


def _register_fake_engine(constants: types.SimpleNamespace) -> None:
    adapter = EngineAdapter(
        personal=constants,
        locations=constants,
        trainers=constants,
        encounters=constants,
        evolutions=constants,
        items=constants,
        machines=constants,
        moves=constants,
        tutors=constants,
        egg_moves=constants,
        learnsets=constants,
        reference_names=constants,
        enrich=constants,
    )
    _ENGINES[_FAKE_ENGINE_ID] = adapter


class EngineContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        _ENGINES.pop(_FAKE_ENGINE_ID, None)

    def test_personal_enrichment_uses_the_registered_engines_member_maps(self) -> None:
        _register_fake_engine(
            types.SimpleNamespace(
                PERSONAL_INTERNAL_MEMBERS={0: "none"},
                PERSONAL_FORM_MEMBERS={},
            )
        )
        self.assertEqual(get_engine(_FAKE_ENGINE_ID).enrich.PERSONAL_FORM_MEMBERS, {})

        pokedb = PokeDBGeneration(
            pokemon_by_id={
                member: {
                    "id": member,
                    "name": f"pokemon-{member}",
                    "species": f"pokemon-{member}",
                }
                for member in range(1, 508)
            },
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )
        records = [_source_record(member) for member in range(508)]

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "personal.narc"},
                "records": records,
            },
            pokedb,
        )

        # Member 0 is the fake engine's only internal record; everything else
        # (unlike gen4_dppt's 494/495 eggs) is public under this engine.
        self.assertFalse(enriched["records"][0]["public"])
        self.assertTrue(enriched["records"][1]["public"])
        self.assertEqual(enriched["public_record_count"], 507)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_pokemon_pages(enriched, output)

        self.assertEqual(count, 507)

    def test_encounter_enrichment_uses_the_registered_engines_slot_chances(self) -> None:
        _register_fake_engine(
            types.SimpleNamespace(
                GEN4_WALKING_SLOT_CHANCES=(999,) + (0,) * 11,
                GEN4_WATER_SLOT_CHANCES=(0,) * 5,
                GEN4_FISHING_SLOT_CHANCES=(0,) * 5,
            )
        )

        data = bytearray(424)
        data[0:4] = (30).to_bytes(4, "little")
        data[4:8] = (5).to_bytes(4, "little")
        data[8:12] = (1).to_bytes(4, "little")
        source = parse_encounter_record(
            bytes(data), area_id=0, archive_path="encounters.narc"
        ).to_dict()
        pokedb = PokeDBGeneration(
            pokemon_by_id={1: {"id": 1, "name": "bulbasaur", "species": "bulbasaur"}},
            pokemon_by_name={},
            pokemon_by_species={},
            abilities_by_id={},
            items_by_id={},
        )

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            pokedb,
        )

        # The 999 sentinel only appears if enrichment read the chance table
        # off the registered fake engine rather than a hardcoded gen4 import.
        self.assertEqual(
            enriched["records"][0]["walking"]["slots"][0]["chance"], 999
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_encounter_pages(enriched, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(catalog["kind"], "encounters")

    def test_unregistered_engine_fails_clearly_instead_of_silently_using_gen4(
        self,
    ) -> None:
        from romwiki.util.errors import DataSourceError

        with self.assertRaisesRegex(DataSourceError, "Unsupported engine"):
            enrich_personal_dataset(
                {
                    "game": "test",
                    "engine": "some-future-engine",
                    "source": {"archive": "personal.narc"},
                    "records": [_source_record(member) for member in range(508)],
                },
                PokeDBGeneration(
                    pokemon_by_id={},
                    pokemon_by_name={},
                    pokemon_by_species={},
                    abilities_by_id={},
                    items_by_id={},
                ),
            )


if __name__ == "__main__":
    unittest.main()
