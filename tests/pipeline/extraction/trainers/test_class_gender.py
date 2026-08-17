from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trainers.class_gender import (
    extract_class_gender_trainer_dataset,
)
from romwiki.profiles.models import GameProfile
from romwiki.schema.pokemon import RecordProvenance
from romwiki.schema.trainers import (
    ClassGenderTrainer,
    TrainerPokemon,
    unresolved_trainer_variant_support,
)
from romwiki.util.errors import InvalidRomError, ProfileError

_PATCH_TARGET = "romwiki.pipeline.extraction.trainers.class_gender"


class ExtractClassGenderTrainerDatasetTests(unittest.TestCase):
    def test_raises_profile_error_for_missing_trainer_metadata(self) -> None:
        profile = _profile(layout={}, parameters={})
        result = _result(profile)

        with self.assertRaisesRegex(ProfileError, "trainer_data"):
            extract_class_gender_trainer_dataset(result)

    def test_rejects_mismatched_trainer_and_party_archive_counts(self) -> None:
        fixture = _Fixture()
        fixture.trainers.members = [SimpleNamespace(index=0), SimpleNamespace(index=1)]
        fixture.parties.members = [SimpleNamespace(index=0)]

        with (
            fixture.patches(),
            self.assertRaisesRegex(InvalidRomError, "different counts"),
        ):
            extract_class_gender_trainer_dataset(fixture.result)

    def test_rejects_a_trainer_name_table_shorter_than_the_trainer_archive(
        self,
    ) -> None:
        fixture = _Fixture()
        fixture.engine.parse_english_message_archive = Mock(
            side_effect=lambda data: {
                b"NAMES": ("Reserved",),
                b"CLASSES": ("Youngster",),
            }[data]
        )

        with (
            fixture.patches(),
            self.assertRaisesRegex(InvalidRomError, "name table is shorter"),
        ):
            extract_class_gender_trainer_dataset(fixture.result)

    def test_builds_the_envelope_and_cross_references_locations(self) -> None:
        fixture = _Fixture()

        with fixture.patches():
            envelope = extract_class_gender_trainer_dataset(fixture.result)

        self.assertEqual(envelope["dataset"], "trainers")
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
            envelope["source"]["trainer_locations"]["events_archive"], "events"
        )
        self.assertEqual(
            envelope["source"]["trainer_script_references"]["scripts_archive"],
            "scripts",
        )
        self.assertEqual(envelope["pokemon_names"], ["MissingNo", "Bulbasaur"])
        self.assertEqual(envelope["battle_families"], [])

    def test_computes_prize_multiplier_provenance_when_configured(self) -> None:
        fixture = _Fixture()
        fixture.profile = replace(
            fixture.profile,
            parameters={
                **fixture.profile.parameters,
                "trainer_class_prize_overlay_id": 9,
                "trainer_class_prize_offset": 100,
            },
        )
        fixture.result = InspectionResult(
            image=fixture.result.image, match=SimpleNamespace(profile=fixture.profile)
        )
        fixture.platform.read_overlay = Mock(return_value=(9, bytes(200)))
        fixture.engine.parse_trainer_class_prize_multipliers = Mock(
            return_value=(150,)
        )

        with fixture.patches():
            envelope = extract_class_gender_trainer_dataset(fixture.result)

        [record] = envelope["records"]
        self.assertEqual(
            record["victory_money_multiplier_provenance"],
            {"source": "rom", "overlay_id": 9, "offset": 100, "class_id": 0},
        )
        self.assertEqual(
            envelope["source"]["trainer_class_prize_multipliers"],
            {"overlay_id": 9, "offset": 100, "count": 1},
        )

    def test_raises_profile_error_for_missing_location_metadata(self) -> None:
        fixture = _Fixture()
        layout = dict(fixture.profile.layout)
        del layout["events"]
        fixture.profile = replace(fixture.profile, layout=layout)
        fixture.result = InspectionResult(
            image=fixture.result.image, match=SimpleNamespace(profile=fixture.profile)
        )

        with (
            fixture.patches(),
            self.assertRaisesRegex(ProfileError, "trainer location metadata"),
        ):
            extract_class_gender_trainer_dataset(fixture.result)

    def test_skips_locations_when_the_engine_reports_no_extraction_support(
        self,
    ) -> None:
        fixture = _Fixture()
        fixture.engine.TRAINER_LOCATION_EXTRACTION = False

        with fixture.patches():
            envelope = extract_class_gender_trainer_dataset(fixture.result)

        [record] = envelope["records"]
        self.assertEqual(record["locations"], ())
        self.assertEqual(record["script_references"], ())
        self.assertEqual(envelope["source"]["trainer_locations"], "unsupported")

    def test_raises_invalid_rom_error_for_an_out_of_range_trainer_object(self) -> None:
        fixture = _Fixture()
        fixture.object_event = SimpleNamespace(
            trainer_type=1, script_id=150, index=0, local_id=0, x=0, y=0, z=0
        )
        fixture.events.read = Mock(return_value=b"EVENTDATA")
        fixture.engine.parse_object_events = Mock(
            return_value=(fixture.object_event,)
        )

        with (
            fixture.patches(),
            self.assertRaisesRegex(InvalidRomError, "resolves to missing trainer"),
        ):
            extract_class_gender_trainer_dataset(fixture.result)


class _Fixture:
    """A fully-mocked class-gender profile with one trainer at one location."""

    def __init__(self) -> None:
        self.profile = _profile(
            layout={
                "trainer_data": "trainer_data",
                "trainer_parties": "trainer_parties",
                "messages": "messages",
                "events": "events",
                "scripts": "scripts",
                "map_names": "map_names",
            },
            parameters={
                "trainer_names_member": 10,
                "trainer_classes_member": 11,
                "trainer_class_gender_offset": 0,
                "map_header_count": 1,
                "map_header_offset": 0,
                "location_names_member": 13,
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
                side_effect=lambda member: {10: b"NAMES", 11: b"CLASSES"}[member]
            )
        )
        self.events = SimpleNamespace(
            members=[SimpleNamespace(index=0)], read=Mock(return_value=b"EVENTDATA")
        )
        self.scripts = SimpleNamespace(
            members=[SimpleNamespace(index=0)], read=Mock(return_value=b"SCRIPTDATA")
        )

        archives_by_marker = {
            b"TRAINERS": self.trainers,
            b"PARTIES": self.parties,
            b"MESSAGES": self.messages,
            b"EVENTS_ARCHIVE": self.events,
            b"SCRIPTS_ARCHIVE": self.scripts,
        }
        path_markers = {
            "trainer_data": b"TRAINERS",
            "trainer_parties": b"PARTIES",
            "messages": b"MESSAGES",
            "events": b"EVENTS_ARCHIVE",
            "scripts": b"SCRIPTS_ARCHIVE",
            "map_names": b"MAP_NAMES_RAW",
        }
        self.filesystem = Mock()
        self.filesystem.read = Mock(
            side_effect=lambda path: path_markers.get(path, b"")
        )

        archive_cls = Mock()
        archive_cls.from_bytes = Mock(
            side_effect=lambda data, **kwargs: archives_by_marker[data]
        )
        self.platform = SimpleNamespace(
            archive_cls=archive_cls,
            filesystem_from_image=Mock(return_value=self.filesystem),
            read_overlay=Mock(),
            read_code_binary=Mock(return_value=b"ARM9" * 200),
        )

        header = SimpleNamespace(
            header_id=5,
            internal_name="map_5",
            location_name_id=0,
            event_file_id=0,
            script_file_id=0,
        )
        self.object_event = SimpleNamespace(
            trainer_type=1, script_id=100, index=2, local_id=2, x=1, y=2, z=3
        )
        command = SimpleNamespace(trainer_ids=[1], offset=42)

        def parse_trainer_record(
            trainer_bytes,
            party_bytes,
            *,
            trainer_id,
            name,
            class_names,
            class_genders,
            class_prize_multipliers,
            trainer_archive,
            party_archive,
        ):
            return ClassGenderTrainer(
                trainer_id=trainer_id,
                name=name,
                class_id=0,
                class_name=class_names[0] if class_names else "",
                class_gender="male",
                victory_money_multiplier=(
                    class_prize_multipliers[0]
                    if class_prize_multipliers is not None
                    else 0
                ),
                has_custom_moves=False,
                has_held_items=False,
                unknown_byte=0,
                party_count=1,
                reward_item_ids=(0, 0, 0, 0),
                ai_flags=0,
                battle_type=0,
                double_battle=False,
                party=(
                    TrainerPokemon(
                        difficulty=0,
                        gender_ability=0,
                        level=5,
                        species_id=1,
                        form_id=0,
                        held_item_id=None,
                        move_ids=(),
                        ball_seal=0,
                    ),
                ),
                trailing_party_data=b"",
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
                }[data]
            ),
            parse_trainer_class_genders=Mock(return_value=("male",)),
            parse_trainer_record=Mock(side_effect=parse_trainer_record),
            parse_object_events=Mock(
                side_effect=lambda data, event_file_id: (self.object_event,)
            ),
            parse_trainer_battle_commands=Mock(return_value=(command,)),
            resolve_trainer_variants=Mock(
                return_value={
                    "battle_families": [],
                    "trainer_variant_support": unresolved_trainer_variant_support(),
                }
            ),
            ARCHIVE_MEMBER_NONE=0xFFFF,
            TRAINER_OBJECT_SCRIPT_START=100,
            TRAINER_OBJECT_SCRIPT_END=200,
            TRAINER_OBJECT_ID_OFFSET=1,
            START_TRAINER_BATTLE=0x1,
            CHECK_WON_BATTLE=0x2,
            FIRST_TRAINER_ID=1,
        )
        self.resolve_map_headers = Mock(return_value=((header,), ("Route 1",)))

    def patches(self):
        return _multi_patch(
            (f"{_PATCH_TARGET}.get_platform", Mock(return_value=self.platform)),
            (
                f"{_PATCH_TARGET}.get_engine",
                Mock(return_value=SimpleNamespace(trainers=self.engine)),
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
            (f"{_PATCH_TARGET}.read_code_binary", Mock(return_value=b"ARM9" * 200)),
            (
                f"{_PATCH_TARGET}.resolve_map_headers",
                Mock(side_effect=lambda *args, **kwargs: self.resolve_map_headers()),
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
        id="test-dppt",
        name="Test Diamond",
        platform="nintendo-ds",
        engine="gen4_dppt",
        base_game="diamond",
        game_codes=("ADAE",),
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
