from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trainers.battle_mode import (
    extract_battle_mode_trainer_dataset,
)
from romwiki.profiles.models import GameProfile
from romwiki.schema.pokemon import RecordProvenance
from romwiki.schema.trainers import (
    AbilitySlotTrainerPokemon,
    BattleModeTrainer,
    unresolved_trainer_variant_support,
)
from romwiki.util.errors import InvalidRomError, ProfileError

_PATCH_TARGET = "romwiki.pipeline.extraction.trainers.battle_mode"


class ExtractBattleModeTrainerDatasetTests(unittest.TestCase):
    def test_raises_profile_error_for_missing_trainer_metadata(self) -> None:
        profile = _profile(layout={}, parameters={})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "trainer_data"):
            extract_battle_mode_trainer_dataset(result)

    def test_rejects_mismatched_trainer_and_party_archive_counts(self) -> None:
        fixture = _Fixture()
        fixture.trainers.members = [SimpleNamespace(index=0), SimpleNamespace(index=1)]
        fixture.parties.members = [SimpleNamespace(index=0)]

        with (
            fixture.patches(),
            self.assertRaisesRegex(InvalidRomError, "different counts"),
        ):
            extract_battle_mode_trainer_dataset(fixture.result)

    def test_rejects_a_trainer_name_table_shorter_than_the_trainer_archive(
        self,
    ) -> None:
        fixture = _Fixture()
        fixture.engine.trainer_name_index = Mock(return_value=99)

        with (
            fixture.patches(),
            self.assertRaisesRegex(InvalidRomError, "name table is shorter"),
        ):
            extract_battle_mode_trainer_dataset(fixture.result)

    def test_builds_the_envelope_and_cross_references_locations(self) -> None:
        fixture = _Fixture()

        with fixture.patches():
            envelope = extract_battle_mode_trainer_dataset(fixture.result)

        self.assertEqual(envelope["dataset"], "trainers")
        self.assertEqual(envelope["game"], fixture.profile.id)
        self.assertEqual(envelope["engine"], fixture.profile.engine)
        self.assertEqual(envelope["record_count"], 1)
        [record] = envelope["records"]
        self.assertEqual(record["trainer_id"], 1)
        self.assertEqual(record["name"], "Ace Trainer Bob")
        self.assertEqual(len(record["locations"]), 1)
        self.assertEqual(record["locations"][0]["name"], "Route 1")
        self.assertEqual(len(record["script_references"]), 1)
        self.assertEqual(envelope["linked_record_count"], 1)
        self.assertEqual(envelope["location_reference_count"], 1)
        self.assertEqual(envelope["script_reference_count"], 1)
        self.assertEqual(
            envelope["source"]["trainer_locations"]["overworld_objects_archive"],
            "overworld_objects",
        )
        self.assertEqual(
            envelope["source"]["trainer_script_references"]["scripts_archive"],
            "scripts",
        )
        self.assertEqual(envelope["pokemon_names"], ["MissingNo", "Bulbasaur"])
        self.assertEqual(envelope["battle_families"], [])

    def test_skips_location_cross_referencing_without_the_required_layout(
        self,
    ) -> None:
        fixture = _Fixture()
        fixture.profile = replace(
            fixture.profile,
            layout={
                key: value
                for key, value in fixture.profile.layout.items()
                if key not in ("map_headers", "scripts", "overworld_objects")
            },
        )
        fixture.result = InspectionResult(
            image=fixture.result.image, match=SimpleNamespace(profile=fixture.profile)
        )

        with fixture.patches():
            envelope = extract_battle_mode_trainer_dataset(fixture.result)

        [record] = envelope["records"]
        self.assertEqual(record["locations"], ())
        self.assertEqual(record["script_references"], ())
        self.assertNotIn("trainer_locations", envelope["source"])
        self.assertNotIn("trainer_script_references", envelope["source"])


class _Fixture:
    """A fully-mocked battle-mode profile with one trainer at one location."""

    def __init__(self) -> None:
        self.profile = _profile(
            layout={
                "trainer_data": "trainer_data",
                "trainer_parties": "trainer_parties",
                "messages": "messages",
                "map_headers": "map_headers",
                "scripts": "scripts",
                "overworld_objects": "overworld_objects",
            },
            parameters={
                "trainer_names_member": 10,
                "trainer_classes_member": 11,
                "map_names_member": 12,
            },
        )
        self.result = _result(self.profile)

        self.trainers = SimpleNamespace(
            members=[SimpleNamespace(index=0), SimpleNamespace(index=1)],
            read=Mock(side_effect=lambda index: f"trainer-{index}".encode()),
        )
        self.parties = SimpleNamespace(
            members=[SimpleNamespace(index=0), SimpleNamespace(index=1)],
            read=Mock(side_effect=lambda index: f"party-{index}".encode()),
        )
        self.messages = SimpleNamespace(
            read=Mock(
                side_effect=lambda member: {10: b"NAMES", 11: b"CLASSES", 12: b"MAPS"}[
                    member
                ]
            )
        )
        self.map_headers_archive = SimpleNamespace(
            read=Mock(return_value=b"MAPHEADERS")
        )
        self.overworld_objects = SimpleNamespace(
            members=[SimpleNamespace(index=0)],
            read=Mock(return_value=b"OWOBJECTS"),
        )
        self.scripts = SimpleNamespace(
            members=[SimpleNamespace(index=0)],
            read=Mock(return_value=b"SCRIPT"),
        )

        archives_by_marker = {
            b"TRAINERS": self.trainers,
            b"PARTIES": self.parties,
            b"MESSAGES": self.messages,
            b"MAPHEADERS_ARCHIVE": self.map_headers_archive,
            b"SCRIPTS_ARCHIVE": self.scripts,
            b"OWOBJECTS_ARCHIVE": self.overworld_objects,
        }
        path_markers = {
            "trainer_data": b"TRAINERS",
            "trainer_parties": b"PARTIES",
            "messages": b"MESSAGES",
            "map_headers": b"MAPHEADERS_ARCHIVE",
            "scripts": b"SCRIPTS_ARCHIVE",
            "overworld_objects": b"OWOBJECTS_ARCHIVE",
        }
        self.filesystem = Mock()
        self.filesystem.read = Mock(side_effect=lambda path: path_markers[path])

        archive_cls = Mock()
        archive_cls.from_bytes = Mock(
            side_effect=lambda data, **kwargs: archives_by_marker[data]
        )
        self.platform = SimpleNamespace(
            archive_cls=archive_cls,
            filesystem_from_image=Mock(return_value=self.filesystem),
        )

        header = SimpleNamespace(header_id=5, overworld_file_id=0, name="Route 1")
        npc = SimpleNamespace(script_used=1234, index=2, x=1, y=2, z=3)
        command = SimpleNamespace(trainer_ids=[1], offset=42)

        def parse_trainer_record(
            trainer_bytes,
            party_bytes,
            *,
            trainer_id,
            name,
            class_names,
            trainer_archive,
            party_archive,
        ):
            return BattleModeTrainer(
                trainer_id=trainer_id,
                name=name,
                class_id=0,
                class_name=class_names[0] if class_names else "",
                battle_mode=0,
                double_battle=False,
                has_custom_moves=False,
                has_held_items=False,
                party_count=1,
                reward_item_ids=(0, 0, 0, 0),
                ai_flags=0,
                healer=False,
                victory_money_multiplier=0,
                victory_item_id=0,
                party=(
                    AbilitySlotTrainerPokemon(
                        iv_strength=0,
                        ability_slot=0,
                        forced_gender_flag=0,
                        level=5,
                        species_id=1,
                        form_id=0,
                        held_item_id=None,
                        move_ids=(),
                    ),
                ),
                provenance=RecordProvenance(
                    source="rom", archive=trainer_archive, member=trainer_id
                ),
                party_provenance=RecordProvenance(
                    source="rom", archive=party_archive, member=trainer_id
                ),
            )

        self.engine = SimpleNamespace(
            parse_english_message_archive=Mock(
                side_effect=lambda data: {
                    b"NAMES": ("Reserved", "Ace Trainer Bob"),
                    b"CLASSES": ("Youngster",),
                    b"MAPS": ("Route 1",),
                }[data]
            ),
            trainer_name_index=Mock(side_effect=lambda index: index),
            parse_trainer_record=Mock(side_effect=parse_trainer_record),
            parse_map_header_table=Mock(return_value=(header,)),
            parse_map_header_script_files=Mock(return_value={5: 0}),
            parse_overworld_npcs=Mock(return_value=(npc,)),
            resolve_common_script_trainer_id=Mock(return_value=1),
            parse_trainer_battle_commands=Mock(return_value=(command,)),
            resolve_trainer_variants=Mock(
                return_value={
                    "battle_families": [],
                    "trainer_variant_support": unresolved_trainer_variant_support(),
                }
            ),
        )

    def patches(self):
        return _multi_patch(
            (f"{_PATCH_TARGET}.get_platform", Mock(return_value=self.platform)),
            (
                f"{_PATCH_TARGET}.get_engine",
                Mock(
                    return_value=SimpleNamespace(
                        trainers=self.engine, capabilities=frozenset()
                    )
                ),
            ),
            (
                f"{_PATCH_TARGET}.extract_reference_names",
                Mock(
                    return_value={
                        "pokemon_names": ["MissingNo", "Bulbasaur"],
                        "name_sources": {},
                    }
                ),
            ),
        )


class _multi_patch:
    def __init__(self, *patches: tuple[str, Mock]) -> None:
        self._patches = [patch(target, new) for target, new in patches]

    def __enter__(self):
        for context in self._patches:
            context.__enter__()
        return self

    def __exit__(self, *args):
        for context in reversed(self._patches):
            context.__exit__(*args)


def _profile(*, layout: dict[str, str], parameters: dict[str, object]) -> GameProfile:
    return GameProfile(
        id="test-bw",
        name="Test Black",
        platform="nintendo-ds",
        engine="gen5_bw",
        base_game="black",
        game_codes=("IRBO",),
        rom_versions=(0,),
        hashes=(),
        layout=layout,
        parameters=parameters,
    )


def _result(profile: GameProfile) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "deadbeef"
    return InspectionResult(image=image, match=SimpleNamespace(profile=profile))


if __name__ == "__main__":
    unittest.main()
