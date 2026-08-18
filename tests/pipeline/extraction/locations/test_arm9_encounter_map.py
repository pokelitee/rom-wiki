from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.locations.arm9_encounter_map import (
    extract_arm9_encounter_map_location_dataset,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.util.errors import InvalidRomError, ProfileError

_MODULE = "romwiki.pipeline.extraction.locations.arm9_encounter_map"

_NULL_ENCOUNTER = 65535
_NULL_EVENT = 65535


class _Archive:
    """Minimal stand-in for the platform archive container."""

    def __init__(self, member_count: int, reader) -> None:
        self.members = tuple(range(member_count))
        self._reader = reader

    def read(self, index: int) -> bytes:
        return self._reader(index)


class _Engine:
    """A gen4-hgss-shaped locations engine stub the module can call."""

    ENCOUNTER_MEMBER_NONE = _NULL_ENCOUNTER
    ARCHIVE_MEMBER_NONE = _NULL_EVENT
    DYNAMIC_WARP_HEADER_ID = -1
    DYNAMIC_WARP_ID = -1
    MATRIX_VOID_HEADER_IDS = ()

    def __init__(
        self, headers, location_names, item_names, events_by_id, matrices=None
    ):
        self._headers = headers
        self._events_by_id = events_by_id
        self._matrices = matrices or {}
        self._messages_by_content = {
            b"location-names": tuple(location_names),
            b"item-names": tuple(item_names),
        }

    def parse_map_headers(self, header_data, map_names_data, count):
        return self._headers

    def parse_english_message_archive(self, data):
        return self._messages_by_content[data]

    def parse_map_events(self, data, event_file_id):
        return self._events_by_id[event_file_id]

    def parse_map_matrix(self, data, matrix_id):
        return self._matrices.get(matrix_id, SimpleNamespace(header_ids=None))

    def resolve_visible_item_id(self, event, item_count):
        return getattr(event, "visible_item_id", None)

    def resolve_hidden_item_id(self, event, item_count):
        return getattr(event, "hidden_item_id", None)

    MAP_HEADER_SIZE = 1


def _header(
    header_id: int,
    *,
    internal_name: str = "ROUTE",
    location_name_id: int = 0,
    encounter_id: int = _NULL_ENCOUNTER,
    event_file_id: int = _NULL_EVENT,
    matrix_id: int = 0,
    script_file_id: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        header_id=header_id,
        internal_name=internal_name,
        location_name_id=location_name_id,
        encounter_id=encounter_id,
        event_file_id=event_file_id,
        matrix_id=matrix_id,
        script_file_id=script_file_id,
    )


def _profile(**parameter_overrides) -> GameProfile:
    parameters = {
        "map_header_count": 1,
        "map_header_offset": 0,
        "location_names_member": 0,
        "item_names_member": 1,
    }
    parameters.update(parameter_overrides)
    return GameProfile(
        id="test-hgss",
        name="Test HGSS",
        platform="nintendo-ds",
        engine="gen4_hgss",
        base_game="heartgold",
        game_codes=("IPKE",),
        rom_versions=(1,),
        hashes=(),
        layout={
            "map_names": "map_names.bin",
            "messages": "messages.narc",
            "encounters": "encounters.narc",
            "events": "events.narc",
            "map_matrices": "matrices.narc",
            "scripts": "scripts.narc",
        },
        parameters=parameters,
    )


def _result(profile: GameProfile) -> InspectionResult:
    match = HashMatch(
        profile=profile,
        known_hash=KnownHash(algorithm="sha256", value="hash", variant="default"),
    )
    image = SimpleNamespace(hashes=SimpleNamespace(sha256="hash"))
    return InspectionResult(image=image, match=match)


def _patched(engine, messages, encounters, events, matrices, scripts=None):
    if scripts is None:
        scripts = _Archive(0, lambda i: b"")
    platform = SimpleNamespace(
        archive_cls=SimpleNamespace(
            from_bytes=lambda data, **kwargs: {
                b"messages.narc": messages,
                b"encounters.narc": encounters,
                b"events.narc": events,
                b"matrices.narc": matrices,
                b"scripts.narc": scripts,
            }[data]
        ),
        filesystem_from_image=lambda image: SimpleNamespace(
            read=lambda path: path.encode()
        ),
        read_code_binary=lambda image: bytes(16),
    )
    return (
        patch(f"{_MODULE}.get_platform", return_value=platform),
        patch(f"{_MODULE}.get_engine", return_value=SimpleNamespace(locations=engine)),
    )


class Arm9EncounterMapDatasetTests(unittest.TestCase):
    def test_raises_profile_error_when_metadata_is_missing(self) -> None:
        profile = _profile()
        profile.layout.pop("encounters")  # type: ignore[attr-defined]
        result = _result(profile)

        with self.assertRaises(ProfileError):
            extract_arm9_encounter_map_location_dataset(
                result, trainer_dataset={"records": []}
            )

    def test_raises_when_a_header_references_a_missing_encounter_member(self) -> None:
        headers = (_header(0, encounter_id=9),)
        engine = _Engine(headers, ("Route 1",), (), {})
        messages = _Archive(2, lambda i: b"location-names" if i == 0 else b"item-names")
        encounters = _Archive(0, lambda i: b"")
        events = _Archive(0, lambda i: b"")
        matrices = _Archive(1, lambda i: b"")
        profile = _profile()
        result = _result(profile)

        get_platform_patch, get_engine_patch = _patched(
            engine, messages, encounters, events, matrices
        )
        with (
            get_platform_patch,
            get_engine_patch,
            self.assertRaises(InvalidRomError),
        ):
            extract_arm9_encounter_map_location_dataset(
                result, trainer_dataset={"records": []}
            )

    def test_raises_when_a_header_references_a_missing_event_file(self) -> None:
        headers = (_header(0, event_file_id=3),)
        engine = _Engine(headers, ("Route 1",), (), {})
        messages = _Archive(2, lambda i: b"location-names" if i == 0 else b"item-names")
        encounters = _Archive(0, lambda i: b"")
        events = _Archive(0, lambda i: b"")
        matrices = _Archive(1, lambda i: b"")
        profile = _profile()
        result = _result(profile)

        get_platform_patch, get_engine_patch = _patched(
            engine, messages, encounters, events, matrices
        )
        with (
            get_platform_patch,
            get_engine_patch,
            self.assertRaises(InvalidRomError),
        ):
            extract_arm9_encounter_map_location_dataset(
                result, trainer_dataset={"records": []}
            )

    def test_raises_when_a_warp_references_a_missing_header(self) -> None:
        headers = (_header(0, event_file_id=0),)
        warp = SimpleNamespace(
            index=0, x=1, z=2, destination_header_id=9, destination_warp_id=0
        )
        events_by_id = {0: SimpleNamespace(warps=(warp,), objects=(), backgrounds=())}
        engine = _Engine(headers, ("Route 1",), (), events_by_id)
        messages = _Archive(2, lambda i: b"location-names" if i == 0 else b"item-names")
        encounters = _Archive(0, lambda i: b"")
        events = _Archive(1, lambda i: b"")
        matrices = _Archive(1, lambda i: b"")
        profile = _profile()
        result = _result(profile)

        get_platform_patch, get_engine_patch = _patched(
            engine, messages, encounters, events, matrices
        )
        with (
            get_platform_patch,
            get_engine_patch,
            self.assertRaises(InvalidRomError),
        ):
            extract_arm9_encounter_map_location_dataset(
                result, trainer_dataset={"records": []}
            )

    def test_builds_a_full_location_dataset(self) -> None:
        item_names = ("NONE", "Potion")
        location_names = ("Route 1", "Route 2")
        dynamic_warp = SimpleNamespace(
            index=0, x=1, z=2, destination_header_id=-1, destination_warp_id=-1
        )
        real_warp = SimpleNamespace(
            index=1, x=3, z=4, destination_header_id=1, destination_warp_id=0
        )
        visible_item_event = SimpleNamespace(
            index=0, visible_item_id=1, x=5, z=6, y=0, hidden_flag=None
        )
        headers = (
            _header(
                0,
                internal_name="ROUTE_01",
                location_name_id=0,
                encounter_id=0,
                event_file_id=0,
                matrix_id=0,
            ),
            _header(
                1,
                internal_name="ROUTE_02",
                location_name_id=1,
                encounter_id=_NULL_ENCOUNTER,
                event_file_id=1,
                matrix_id=0,
            ),
        )
        events_by_id = {
            0: SimpleNamespace(
                warps=(dynamic_warp, real_warp),
                objects=(visible_item_event,),
                backgrounds=(),
            ),
            1: SimpleNamespace(warps=(), objects=(), backgrounds=()),
        }
        engine = _Engine(headers, location_names, item_names, events_by_id)
        messages = _Archive(2, lambda i: b"location-names" if i == 0 else b"item-names")
        encounters = _Archive(1, lambda i: b"")
        events = _Archive(2, lambda i: b"")
        matrices = _Archive(1, lambda i: b"")
        profile = _profile()
        result = _result(profile)

        get_platform_patch, get_engine_patch = _patched(
            engine, messages, encounters, events, matrices
        )
        with get_platform_patch, get_engine_patch:
            dataset = extract_arm9_encounter_map_location_dataset(
                result, trainer_dataset={"records": []}
            )

        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["warp_count"], 2)
        self.assertEqual(dataset["visible_item_count"], 1)
        self.assertEqual(dataset["hidden_item_count"], 0)
        self.assertEqual(dataset["source"]["rom_sha256"], "hash")

        first = dataset["records"][0]
        self.assertEqual(first["name"], "Route 1")
        self.assertEqual(first["internal_name"], "ROUTE_01")
        self.assertEqual(first["encounter_map_index"], 0)
        self.assertEqual(len(first["items"]), 1)
        self.assertEqual(first["items"][0]["item_id"], 1)
        self.assertEqual(first["items"][0]["name"], "Potion")
        self.assertEqual(first["items"][0]["kind"], "visible")

        warps = first["warps"]
        self.assertTrue(warps[0]["dynamic"])
        self.assertIsNone(warps[0]["destination_header_id"])
        self.assertFalse(warps[1]["dynamic"])
        self.assertEqual(warps[1]["destination_header_id"], 1)
        self.assertEqual(warps[1]["destination_name"], "Route 2")
        self.assertFalse(warps[1]["destination_warp_exists"])

        second = dataset["records"][1]
        self.assertIsNone(second["encounter_map_index"])
        self.assertEqual(second["items"], ())


if __name__ == "__main__":
    unittest.main()
