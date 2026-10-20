from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from romwiki.engines.registry import (
    EngineAdapter,
    EngineFormats,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.pickup import extract_pickup_dataset
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.versions import PICKUP_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, ProfileError

_PLATFORM_ID = "fake-pickup-platform"
_ENGINE_ID = "fake_pickup_engine"


def _register_fake_platform(
    *, read_overlay: Mock | None = None, read_overlay_decompressed: Mock | None = None
) -> Mock:
    archive_cls = Mock()
    messages_archive = Mock()
    archive_cls.from_bytes.return_value = messages_archive
    register_platform(
        _PLATFORM_ID,
        PlatformAdapter(
            inspect=lambda path: None,
            filesystem_from_image=lambda image: Mock(read=Mock(return_value=b"raw")),
            matches_header=lambda image, codes, versions: True,
            archive_cls=archive_cls,
            read_overlay=read_overlay,
            read_overlay_decompressed=read_overlay_decompressed,
        ),
    )
    return messages_archive


def _register_fake_engine(
    *, pickup: SimpleNamespace, items: SimpleNamespace | None = None, pickup_format: str
) -> None:
    fields: dict[str, Any] = dict.fromkeys(
        EngineAdapter.__dataclass_fields__, SimpleNamespace()
    )
    fields["pickup"] = pickup
    if items is not None:
        fields["items"] = items
    fields["generation"] = None
    fields["dataset_kinds"] = frozenset({"pokemon"})
    fields["required_dataset_kinds"] = frozenset({"pokemon"})
    fields["formats"] = EngineFormats(
        encounters="unsupported",
        locations="unsupported",
        location_extraction="unsupported",
        pickup=pickup_format,
        trainers="unsupported",
        tutors="none",
        fossils="none",
        static_encounters="none",
        egg_moves="none",
        item_archive="archive-index",
        machines="none",
    )
    register_engine(_ENGINE_ID, EngineAdapter(**fields), validate=False)


def _profile(**overrides: object) -> GameProfile:
    defaults: dict[str, Any] = {
        "id": "test-pickup",
        "name": "Test Pickup",
        "platform": _PLATFORM_ID,
        "engine": _ENGINE_ID,
        "base_game": "test",
        "game_codes": (),
        "rom_versions": (),
        "hashes": (KnownHash(algorithm="sha256", value="abc123", variant="retail"),),
        "layout": {"messages": "messages.narc"},
        "parameters": {},
    }
    defaults.update(overrides)
    return GameProfile(**defaults)


def _result(profile: GameProfile | None) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "abc123"
    match = None
    if profile is not None:
        match = HashMatch(profile=profile, known_hash=profile.hashes[0])
    return InspectionResult(image=image, match=match)


class ExtractPickupDatasetTests(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_platform(_PLATFORM_ID)
        unregister_engine(_ENGINE_ID)

    def test_raises_without_a_matched_profile(self) -> None:
        with self.assertRaisesRegex(
            ProfileError, "known game profile is required for pickup"
        ):
            extract_pickup_dataset(_result(None))

    def test_raises_for_an_engine_without_pickup_support(self) -> None:
        profile = _profile(parameters={"pickup_overlay_id": 1, "item_names_member": 2})
        _register_fake_platform()
        _register_fake_engine(pickup=SimpleNamespace(), pickup_format="none")

        with self.assertRaisesRegex(
            DataSourceError, "does not provide pickup extraction"
        ):
            extract_pickup_dataset(_result(profile))

    def test_split_table_raises_when_metadata_is_missing(self) -> None:
        profile = _profile(parameters={})
        _register_fake_platform()
        _register_fake_engine(pickup=SimpleNamespace(), pickup_format="split-table")

        with self.assertRaisesRegex(ProfileError, "is missing pickup metadata"):
            extract_pickup_dataset(_result(profile))

    def test_split_table_extraction_builds_item_tables(self) -> None:
        profile = _profile(
            parameters={
                "pickup_overlay_id": 5,
                "pickup_common_items_offset": 0x10,
                "pickup_rare_items_offset": 0x20,
                "pickup_common_rate_offset": 0x30,
                "pickup_honey_gather_rate_offset": 0x40,
                "item_names_member": 7,
            }
        )
        _register_fake_platform(read_overlay=Mock(return_value=(5, b"overlaydata")))
        tables = SimpleNamespace(
            common_item_ids=[0, 1],
            rare_item_ids=[2],
            common_rate=[10, 20],
            honey_gather_rate=[5],
        )
        parse_pickup_tables = Mock(return_value=tables)
        _register_fake_engine(
            pickup=SimpleNamespace(
                parse_english_message_archive=Mock(
                    return_value=("Potion", "Antidote", "Awakening")
                ),
                parse_pickup_tables=parse_pickup_tables,
                PICKUP_COMMON_ITEM_COUNT=2,
                PICKUP_RARE_ITEM_COUNT=1,
                PICKUP_COMMON_RATE_COUNT=2,
                PICKUP_HONEY_GATHER_RATE_COUNT=1,
            ),
            pickup_format="split-table",
        )

        dataset = extract_pickup_dataset(_result(profile))

        self.assertEqual(dataset["schema_version"], PICKUP_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "pickup")
        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(
            dataset["tables"]["common_items"],
            [{"item_id": 0, "name": "Potion"}, {"item_id": 1, "name": "Antidote"}],
        )
        self.assertEqual(
            dataset["tables"]["rare_items"], [{"item_id": 2, "name": "Awakening"}]
        )
        self.assertEqual(dataset["tables"]["common_rate"], [10, 20])
        self.assertEqual(dataset["tables"]["honey_gather_rate"], [5])
        self.assertEqual(dataset["source"], {"rom_sha256": "abc123", "overlay_id": 5})
        self.assertEqual(parse_pickup_tables.call_args.kwargs["common_count"], 2)
        self.assertEqual(parse_pickup_tables.call_args.kwargs["item_count"], 3)

    def test_split_table_honors_parameter_overridden_counts(self) -> None:
        profile = _profile(
            parameters={
                "pickup_overlay_id": 5,
                "pickup_common_items_offset": 0x10,
                "pickup_rare_items_offset": 0x20,
                "pickup_common_rate_offset": 0x30,
                "pickup_honey_gather_rate_offset": 0x40,
                "item_names_member": 7,
                "pickup_common_item_count": 99,
            }
        )
        _register_fake_platform(read_overlay=Mock(return_value=(5, b"overlaydata")))
        parse_pickup_tables = Mock(
            return_value=SimpleNamespace(
                common_item_ids=[],
                rare_item_ids=[],
                common_rate=[],
                honey_gather_rate=[],
            )
        )
        _register_fake_engine(
            pickup=SimpleNamespace(
                parse_english_message_archive=Mock(return_value=()),
                parse_pickup_tables=parse_pickup_tables,
                PICKUP_COMMON_ITEM_COUNT=2,
                PICKUP_RARE_ITEM_COUNT=1,
                PICKUP_COMMON_RATE_COUNT=2,
                PICKUP_HONEY_GATHER_RATE_COUNT=1,
            ),
            pickup_format="split-table",
        )

        extract_pickup_dataset(_result(profile))

        self.assertEqual(parse_pickup_tables.call_args.kwargs["common_count"], 99)

    def test_locator_tables_raises_when_metadata_is_missing(self) -> None:
        profile = _profile(parameters={})
        _register_fake_platform()
        _register_fake_engine(pickup=SimpleNamespace(), pickup_format="locator-tables")

        with self.assertRaisesRegex(ProfileError, "is missing pickup metadata"):
            extract_pickup_dataset(_result(profile))

    def test_locator_tables_extraction_builds_level_ranges(self) -> None:
        profile = _profile(parameters={"pickup_overlay_id": 9, "item_names_member": 3})
        _register_fake_platform(
            read_overlay_decompressed=Mock(
                return_value=(SimpleNamespace(id=9, file_id=42), b"overlaydata")
            )
        )
        item_names = tuple(f"Item{index}" for index in range(20))
        parse_pickup_item_table = Mock(side_effect=[(0, 1), (2, 3)])
        pickup_level_range_item_ids = Mock(return_value=(0, 1))
        _register_fake_engine(
            pickup=SimpleNamespace(
                parse_english_message_archive=Mock(return_value=item_names),
                PICKUP_COMMON_TABLE_LOCATOR="aa",
                PICKUP_RARE_TABLE_LOCATOR="bb",
                PICKUP_COMMON_ITEM_COUNT=2,
                PICKUP_RARE_ITEM_COUNT=2,
                parse_pickup_item_table=parse_pickup_item_table,
                PICKUP_LEVEL_RANGE_COUNT=2,
                PICKUP_LEVEL_RANGE_SIZE=10,
                pickup_level_range_item_ids=pickup_level_range_item_ids,
                PICKUP_SLOT_CHANCES=(80, 20),
            ),
            pickup_format="locator-tables",
        )

        with patch(
            "romwiki.pipeline.extraction.pickup.find_unique_pattern",
            side_effect=[111, 222],
        ):
            dataset = extract_pickup_dataset(_result(profile))

        self.assertEqual(len(dataset["level_ranges"]), 2)
        first = dataset["level_ranges"][0]
        self.assertEqual(first["minimum_level"], 1)
        self.assertEqual(first["maximum_level"], 10)
        self.assertEqual(
            first["slots"],
            [
                {"item_id": 0, "name": "Item0", "chance": 80},
                {"item_id": 1, "name": "Item1", "chance": 20},
            ],
        )
        second = dataset["level_ranges"][1]
        self.assertEqual(second["minimum_level"], 11)
        self.assertEqual(second["maximum_level"], 20)
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "abc123",
                "overlay_id": 9,
                "file_id": 42,
                "common_offset": 111,
                "rare_offset": 222,
            },
        )

    def test_sliding_table_raises_when_metadata_is_missing(self) -> None:
        profile = _profile(parameters={})
        _register_fake_platform()
        _register_fake_engine(pickup=SimpleNamespace(), pickup_format="sliding-table")

        with self.assertRaisesRegex(ProfileError, "is missing pickup metadata"):
            extract_pickup_dataset(_result(profile))

    def test_sliding_table_extraction_builds_level_ranges(self) -> None:
        profile = _profile(parameters={"pickup_overlay_id": 4, "item_names_member": 1})
        _register_fake_platform(
            read_overlay_decompressed=Mock(
                return_value=(SimpleNamespace(id=4), b"overlaydata")
            )
        )
        item_names = tuple(f"Item{index}" for index in range(5))
        _register_fake_engine(
            items=SimpleNamespace(
                parse_english_message_archive=Mock(return_value=item_names)
            ),
            pickup=SimpleNamespace(
                PICKUP_TABLE_LOCATOR="cc",
                parse_pickup_table=Mock(
                    return_value=SimpleNamespace(item_ids=(0, 1, 2))
                ),
                PICKUP_LEVEL_RANGE_COUNT=1,
                PICKUP_LEVEL_RANGE_SIZE=100,
                pickup_level_range_item_ids=Mock(return_value=(0, 1, 2)),
                PICKUP_SLOT_CHANCES=(50, 30, 20),
            ),
            pickup_format="sliding-table",
        )

        with patch(
            "romwiki.pipeline.extraction.pickup.find_unique_pattern", return_value=555
        ) as find_pattern:
            dataset = extract_pickup_dataset(_result(profile))

        self.assertEqual(
            dataset["level_ranges"][0]["slots"],
            [
                {"item_id": 0, "name": "Item0", "chance": 50},
                {"item_id": 1, "name": "Item1", "chance": 30},
                {"item_id": 2, "name": "Item2", "chance": 20},
            ],
        )
        self.assertEqual(
            dataset["source"],
            {"rom_sha256": "abc123", "overlay_id": 4, "table_offset": 555},
        )
        find_pattern.assert_called_once()
        self.assertEqual(find_pattern.call_args.args[1], bytes.fromhex("cc"))

    def test_sliding_table_honors_a_profile_overridden_locator(self) -> None:
        profile = _profile(
            parameters={
                "pickup_overlay_id": 4,
                "item_names_member": 1,
                "pickup_table_locator": "dd",
            }
        )
        _register_fake_platform(
            read_overlay_decompressed=Mock(
                return_value=(SimpleNamespace(id=4), b"overlaydata")
            )
        )
        _register_fake_engine(
            items=SimpleNamespace(parse_english_message_archive=Mock(return_value=())),
            pickup=SimpleNamespace(
                PICKUP_TABLE_LOCATOR="cc",
                parse_pickup_table=Mock(return_value=SimpleNamespace(item_ids=())),
                PICKUP_LEVEL_RANGE_COUNT=0,
                PICKUP_LEVEL_RANGE_SIZE=100,
                pickup_level_range_item_ids=Mock(return_value=()),
                PICKUP_SLOT_CHANCES=(),
            ),
            pickup_format="sliding-table",
        )

        with patch(
            "romwiki.pipeline.extraction.pickup.find_unique_pattern", return_value=1
        ) as find_pattern:
            extract_pickup_dataset(_result(profile))

        self.assertEqual(find_pattern.call_args.args[1], bytes.fromhex("dd"))


if __name__ == "__main__":
    unittest.main()
