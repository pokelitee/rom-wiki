"""Proves the enrichment and rendering layers hold no gen4_dppt-specific
branches or constants: a fake engine registered only for these tests uses
deliberately different table shapes (4 personal records, 3 moves, 3 types)
and must flow through unmodified, exactly as a real second engine would.
"""

from __future__ import annotations

import json
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path

from romwiki.engines.gen4.dppt import parse_encounter_record
from romwiki.engines.profile_contracts import EngineProfileContract
from romwiki.engines.registry import (
    GEN5_B2W2_ENGINE,
    EngineAdapter,
    EngineFormats,
    get_engine,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.enrichment.abilities import build_ability_dataset
from romwiki.pipeline.enrichment.encounters import enrich_encounter_dataset
from romwiki.pipeline.enrichment.moves import enrich_move_dataset
from romwiki.pipeline.enrichment.pokemon import enrich_personal_dataset
from romwiki.pipeline.enrichment.trainers import enrich_trainer_dataset
from romwiki.renderers.mkdocs import (
    render_ability_pages,
    render_encounter_pages,
    render_move_pages,
    render_pokemon_pages,
    render_trainer_pages,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError

_FAKE_ENGINE_ID = "fake_test_engine"
_FAKE_PERSONAL_COUNT = 4
_FAKE_MOVE_COUNT = 3


def _fake_engine_tables(**overrides: object) -> types.SimpleNamespace:
    """A minimal engine contract with shapes unlike gen4_dppt's."""
    values: dict[str, object] = {
        "PERSONAL_RECORD_COUNT": _FAKE_PERSONAL_COUNT,
        "MOVE_RECORD_COUNT": _FAKE_MOVE_COUNT,
        "MAX_MOVE_ID": _FAKE_MOVE_COUNT - 1,
        "BASE_SPECIES_COUNT": _FAKE_PERSONAL_COUNT - 1,
        "MACHINE_COUNT": 2,
        "TYPE_NAME_COUNT": 3,
        "ABILITY_NAME_COUNT": 3,
        "ITEM_NAME_COUNT": 3,
        "MOVE_NAME_COUNT": _FAKE_MOVE_COUNT,
        "POKEMON_NAME_COUNT": _FAKE_PERSONAL_COUNT,
        "INTERNAL_MEMBERS": {0: "none"},
        "FORM_MEMBERS": {},
        "TRAINER_FORM_SLUGS": {},
        "TRAINER_COSMETIC_FORM_LABELS": {},
        "TYPE_NAMES": ("neutral", "flame", "aqua"),
        "DAMAGE_CLASS_NAMES": ("contact", "ranged"),
        "GROWTH_RATE_NAMES": ("steady",),
        "EGG_GROUP_NAMES": ("none", "blob"),
        "COLOR_NAMES": ("red", "blue"),
        "EVOLUTION_METHOD_NAMES": ("none", "level"),
        "EVOLUTION_PARAMETER_KINDS": {1: "level"},
        "machine_name": lambda machine_id: f"DISC{machine_id:02}",
        "WALKING_SLOT_CHANCES": (999,) + (0,) * 11,
        "WATER_SLOT_CHANCES": (0,) * 5,
        "FISHING_SLOT_CHANCES": (0,) * 5,
        "BONUS_SLOT_METHODOLOGY_SOURCE": "the fake test engine's own routine",
        "SWARM_SLOT_INDICES": (1, 2),
        "TIMED_SLOT_INDICES": (3, 4),
        "DUAL_SLOT_SLOT_INDICES": (9, 10),
        "UNOWN_FORM_NAMES": ("Q", "R"),
        "UNOWN_FORM_TABLES": ((0,), (1,)),
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _register_fake_engine(tables: types.SimpleNamespace) -> None:
    adapter = EngineAdapter(
        personal=tables,
        locations=tables,
        trainers=tables,
        encounters=tables,
        evolutions=tables,
        items=tables,
        machines=tables,
        moves=tables,
        tutors=tables,
        egg_moves=tables,
        learnsets=tables,
        reference_names=tables,
        enrich=tables,
        trainer_party=tables,
        trades=tables,
        marts=tables,
        static_encounters=tables,
        pickup=tables,
        formats=EngineFormats(
            encounters="conditional",
            locations="event-map",
            location_extraction="arm9-event-map",
            pickup="split-table",
            trainers="class-gender",
            tutors="none",
            fossils="none",
            static_encounters="none",
            egg_moves="none",
            item_archive="archive-index",
            machines="none",
        ),
    )
    register_engine(_FAKE_ENGINE_ID, adapter, validate=False)


def _fake_pokedb() -> PokeDBGeneration:
    pokemon = {
        member: {
            "id": member,
            "name": f"fakemon-{member}",
            "species": f"fakemon-{member}",
        }
        for member in range(1, _FAKE_PERSONAL_COUNT)
    }
    return PokeDBGeneration(
        pokemon_by_id=pokemon,
        pokemon_by_name={},
        pokemon_by_species={},
        abilities_by_id={1: "sturdy-shell", 2: "hot-streak"},
        items_by_id={1: "berry", 2: "charm"},
        moves_by_id={1: "bump", 2: "splash-kick"},
    )


def _fake_personal_record(member: int) -> dict:
    return {
        "species_id": member,
        "base_stats": {
            "hp": 40,
            "attack": 40,
            "defense": 40,
            "speed": 40,
            "special_attack": 40,
            "special_defense": 40,
        },
        "type_ids": [1, 2],
        "catch_rate": 100,
        "base_experience": 50,
        "ev_yields": {
            "hp": 0,
            "attack": 1,
            "defense": 0,
            "speed": 0,
            "special_attack": 0,
            "special_defense": 0,
        },
        "wild_held_items": {"common": 0, "rare": 0},
        "gender_ratio": 127,
        "hatch_cycles": 20,
        "base_friendship": 70,
        "growth_rate_id": 0,
        "egg_group_ids": [1, 1],
        "ability_ids": [1, 0],
        "safari_flee_rate": 0,
        "body_color_id": 1,
        "flip_sprite": False,
        "machine_ids": [],
        "machine_masks": [0, 0, 0, 0],
        "provenance": {"source": "rom", "archive": "fake.bin", "member": member},
    }


def _fake_move_record(move_id: int) -> dict:
    return {
        "move_id": move_id,
        "effect_id": 0,
        "damage_class_id": 1,
        "power": 40,
        "type_id": 2,
        "accuracy": 100,
        "pp": 20,
        "effect_chance": 0,
        "target_id": 0,
        "priority": 0,
        "flags": 0,
        "contest_effect_id": 0,
        "contest_type_id": 0,
        "provenance": {"source": "rom", "archive": "fake.bin", "member": move_id},
    }


class EngineContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_engine(_FAKE_ENGINE_ID)

    def test_b2w2_uses_its_personal_layout_with_shared_gen5_tables(self) -> None:
        engine = get_engine(GEN5_B2W2_ENGINE)

        self.assertEqual(engine.generation, 5)
        self.assertEqual(engine.personal.PERSONAL_RECORD_COUNT, 709)
        self.assertEqual(engine.enrich.PERSONAL_RECORD_COUNT, 709)
        self.assertEqual(engine.enrich.MOVE_RECORD_COUNT, 560)

    def test_registration_rejects_an_incomplete_concern(self) -> None:
        adapter = replace(
            get_engine(GEN5_B2W2_ENGINE), personal=types.SimpleNamespace()
        )

        with self.assertRaisesRegex(DataSourceError, "parse_personal_record"):
            register_engine(_FAKE_ENGINE_ID, adapter)

    def test_registration_rejects_an_unknown_semantic_format(self) -> None:
        source = get_engine(GEN5_B2W2_ENGINE)
        adapter = replace(
            source,
            formats=replace(source.formats, encounters="seasonel"),
        )

        with self.assertRaisesRegex(DataSourceError, "invalid formats.*seasonel"):
            register_engine(_FAKE_ENGINE_ID, adapter)

    def test_registration_rejects_mismatched_location_contracts(self) -> None:
        source = get_engine(GEN5_B2W2_ENGINE)
        adapter = replace(
            source,
            formats=replace(source.formats, location_extraction="arm9-event-map"),
        )

        with self.assertRaisesRegex(
            DataSourceError, "arm9-event-map.*requires normalized shape 'event-map'"
        ):
            register_engine(_FAKE_ENGINE_ID, adapter)

    def test_partial_engine_validates_only_its_declared_dataset_sections(self) -> None:
        source = get_engine(GEN5_B2W2_ENGINE)
        minimal = replace(
            source,
            moves=types.SimpleNamespace(),
            items=types.SimpleNamespace(),
            encounters=types.SimpleNamespace(),
            trainers=types.SimpleNamespace(),
            locations=types.SimpleNamespace(),
            trainer_party=types.SimpleNamespace(),
            pickup=types.SimpleNamespace(),
            tutors=types.SimpleNamespace(),
            static_encounters=types.SimpleNamespace(),
            formats=replace(
                source.formats,
                pickup="none",
                tutors="none",
                fossils="none",
                static_encounters="none",
            ),
            dataset_kinds=frozenset({"pokemon", "abilities"}),
            required_dataset_kinds=frozenset({"pokemon"}),
            profile_contract=EngineProfileContract(
                required_layout=frozenset({"personal"}),
                optional_layout=frozenset({"moves", "encounters"}),
                reject_unknown=True,
            ),
        )

        register_engine(_FAKE_ENGINE_ID, minimal)

        self.assertEqual(
            get_engine(_FAKE_ENGINE_ID).dataset_kinds,
            frozenset({"pokemon", "abilities"}),
        )

    def test_registration_rejects_required_dataset_the_engine_does_not_support(
        self,
    ) -> None:
        adapter = replace(
            get_engine(GEN5_B2W2_ENGINE),
            dataset_kinds=frozenset({"pokemon"}),
            required_dataset_kinds=frozenset({"pokemon", "moves"}),
        )

        with self.assertRaisesRegex(DataSourceError, "requires unsupported.*moves"):
            register_engine(_FAKE_ENGINE_ID, adapter)

    def test_registration_rejects_unsupported_dataset_dependencies(self) -> None:
        adapter = replace(
            get_engine(GEN5_B2W2_ENGINE),
            dataset_kinds=frozenset({"pokemon", "trainers"}),
            required_dataset_kinds=frozenset({"pokemon"}),
        )

        with self.assertRaisesRegex(
            DataSourceError, "dataset 'trainers'.*requires supported datasets: moves"
        ):
            register_engine(_FAKE_ENGINE_ID, adapter)

    def test_personal_enrichment_uses_the_engines_shapes_not_gen4_constants(
        self,
    ) -> None:
        _register_fake_engine(_fake_engine_tables())
        records = [
            _fake_personal_record(member) for member in range(_FAKE_PERSONAL_COUNT)
        ]
        records[0]["type_ids"] = [255, 255]
        records[0]["growth_rate_id"] = 255
        records[0]["egg_group_ids"] = [255, 255]
        records[0]["ability_ids"] = [255, 255]
        records[0]["body_color_id"] = 255

        enriched = enrich_personal_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "fake.bin"},
                "records": records,
            },
            _fake_pokedb(),
        )

        self.assertFalse(enriched["records"][0]["public"])
        self.assertEqual(enriched["public_record_count"], _FAKE_PERSONAL_COUNT - 1)
        self.assertEqual(enriched["records"][1]["types"][0]["name"], "flame")
        self.assertEqual(enriched["records"][1]["growth_rate"]["name"], "steady")
        self.assertEqual(enriched["records"][1]["egg_groups"][0]["name"], "blob")

        with tempfile.TemporaryDirectory() as directory:
            count = render_pokemon_pages(enriched, Path(directory))
        self.assertEqual(count, _FAKE_PERSONAL_COUNT - 1)

    def test_personal_enrichment_rejects_gen4_sized_input_for_other_engines(
        self,
    ) -> None:
        _register_fake_engine(_fake_engine_tables())
        records = [_fake_personal_record(member) for member in range(508)]

        with self.assertRaisesRegex(DataSourceError, "Expected exactly 4"):
            enrich_personal_dataset(
                {
                    "game": "test",
                    "engine": _FAKE_ENGINE_ID,
                    "source": {"archive": "fake.bin"},
                    "records": records,
                },
                _fake_pokedb(),
            )

    def test_move_enrichment_uses_the_engines_shapes(self) -> None:
        _register_fake_engine(_fake_engine_tables())
        records = [_fake_move_record(move_id) for move_id in range(_FAKE_MOVE_COUNT)]

        enriched = enrich_move_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "fake.bin"},
                "records": records,
            },
            _fake_pokedb(),
        )

        self.assertEqual(enriched["public_record_count"], _FAKE_MOVE_COUNT - 1)
        self.assertEqual(enriched["records"][1]["damage_class"]["name"], "ranged")
        self.assertEqual(enriched["records"][1]["type"]["name"], "aqua")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            count = render_move_pages(enriched, output)
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(count, _FAKE_MOVE_COUNT - 1)
        self.assertEqual(catalog["kind"], "moves")

    def test_trainer_enrichment_uses_the_engines_party_normalization(self) -> None:
        stats = (
            "hp",
            "attack",
            "defense",
            "special_attack",
            "special_defense",
            "speed",
        )

        def normalize(member, has_custom_moves):
            return {
                "species_id": member["species_id"],
                "form_id": member["form_id"],
                "level": member["level"],
                "held_item_id": member["held_item_id"],
                "move_ids": list(member["move_ids"]) if has_custom_moves else [],
                "moves_source": "explicit" if has_custom_moves else "level-up",
                "ability": None,
                "nature": None,
                "gender": None,
                "ivs": None,
                "evs": None,
                "calculated_stats": None,
                "source_fields": {},
            }

        def derive(member, **_kwargs):
            return {
                **member,
                "nature": {"source": "derived", "name": "Sturdy"},
                "calculated_stats": {
                    "source": "derived",
                    "values": dict.fromkeys(stats, 50),
                },
            }

        _register_fake_engine(
            _fake_engine_tables(
                normalize_trainer_party_member=normalize,
                derive_trainer_party_attributes=derive,
            )
        )
        enriched = enrich_trainer_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "fake.bin"},
                "records": [
                    {
                        "trainer_id": 0,
                        "name": "Blank",
                        "class_id": 0,
                        "class_name": "Tester",
                        "class_gender": "female",
                        "has_custom_moves": True,
                        "has_held_items": False,
                        "unknown_byte": 0,
                        "party_count": 1,
                        "reward_item_ids": [0, 0, 0, 0],
                        "ai_flags": 0,
                        "battle_type": 0,
                        "double_battle": False,
                        "party": [
                            {
                                "species_id": 1,
                                "form_id": 0,
                                "level": 10,
                                "held_item_id": None,
                                "move_ids": [1, 2, 0, 0],
                            }
                        ],
                        "locations": [],
                        "script_references": [],
                        "provenance": {"archive": "fake.bin", "member": 0},
                        "party_provenance": {"archive": "fake.bin", "member": 0},
                    }
                ],
            },
            _fake_pokedb(),
        )

        member = enriched["records"][0]["party"][0]
        self.assertEqual(member["nature"]["name"], "Sturdy")
        self.assertEqual(member["pokemon"]["name"], "Fakemon 1")
        self.assertEqual(
            [move["name"] for move in member["moves"]], ["bump", "splash-kick"]
        )

        with tempfile.TemporaryDirectory() as directory:
            count = render_trainer_pages(enriched, Path(directory))
        self.assertEqual(count, 1)

    def test_ability_dataset_uses_the_engines_name_count(self) -> None:
        _register_fake_engine(_fake_engine_tables())
        dataset = build_ability_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "dataset": "pokemon",
                "source": {"archive": "fake.bin"},
                "ability_names": ["-", "Sturdy Shell", "Hot Streak"],
                "records": [
                    {
                        "member": 1,
                        "national_dex_id": 1,
                        "slug": "fakemon-1",
                        "name": "Fakemon 1",
                        "public": True,
                        "abilities": [
                            {"id": 1, "slug": "sturdy-shell", "name": "Sturdy Shell"}
                        ],
                    }
                ],
            },
            _fake_pokedb(),
        )

        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["records"][0]["name"], "Sturdy Shell")

        with tempfile.TemporaryDirectory() as directory:
            count = render_ability_pages(dataset, Path(directory))
        self.assertEqual(count, 2)

    def test_encounter_enrichment_uses_the_registered_engines_slot_chances(
        self,
    ) -> None:
        _register_fake_engine(_fake_engine_tables())

        data = bytearray(424)
        data[0:4] = (30).to_bytes(4, "little")
        data[4:8] = (5).to_bytes(4, "little")
        data[8:12] = (1).to_bytes(4, "little")
        source = parse_encounter_record(
            bytes(data), area_id=0, archive_path="encounters.narc"
        ).to_dict()

        enriched = enrich_encounter_dataset(
            {
                "game": "test",
                "engine": _FAKE_ENGINE_ID,
                "source": {"archive": "encounters.narc"},
                "records": [source],
            },
            _fake_pokedb(),
        )

        # The 999 sentinel only appears if enrichment read the chance table
        # off the registered fake engine rather than a hardcoded gen4 import.
        self.assertEqual(enriched["records"][0]["walking"]["slots"][0]["chance"], 999)
        # Likewise for the bonus-slot methodology citation: it must come from
        # the registered engine, not a literal gen4/Platinum string baked
        # into the renderer.
        self.assertEqual(
            enriched["records"][0]["bonus_slot_methodology_source"],
            "the fake test engine's own routine",
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
        with self.assertRaisesRegex(DataSourceError, "Unsupported engine"):
            enrich_personal_dataset(
                {
                    "game": "test",
                    "engine": "some-future-engine",
                    "source": {"archive": "personal.narc"},
                    "records": [],
                },
                _fake_pokedb(),
            )


if __name__ == "__main__":
    unittest.main()
