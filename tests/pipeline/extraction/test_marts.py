from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from romwiki.pipeline.extraction.marts import _shop_records, extract_mart_dataset
from romwiki.profiles.models import GameProfile
from romwiki.schema import RecordProvenance, Shop
from romwiki.schema.versions import MARTS_RAW_SCHEMA_VERSION
from romwiki.util.errors import ProfileError


class _FakeArchive:
    def __init__(self, blobs: dict[int, bytes], member_count: int) -> None:
        self._blobs = blobs
        self.members = tuple(range(member_count))

    def read(self, index: int) -> bytes:
        return self._blobs[index]


class _FakeArchiveCls:
    def __init__(self, registry: dict[bytes, _FakeArchive]) -> None:
        self._registry = registry

    def from_bytes(self, data: bytes, allow_truncated: bool = False) -> _FakeArchive:
        return self._registry[data]


class _FakeFilesystem:
    def __init__(self, data: dict[str, bytes]) -> None:
        self._data = data

    def read(self, path: str) -> bytes:
        return self._data[path]


def _fake_platform(
    filesystem_data: dict[str, bytes],
    archive_registry: dict[bytes, _FakeArchive],
    **extra: object,
) -> SimpleNamespace:
    return SimpleNamespace(
        filesystem_from_image=lambda image: _FakeFilesystem(filesystem_data),
        archive_cls=_FakeArchiveCls(archive_registry),
        **extra,
    )


def _profile(**overrides: object) -> GameProfile:
    fields: dict[str, Any] = {
        "id": "test",
        "name": "Test",
        "platform": "nintendo-ds",
        "engine": "gen5_bw",
        "base_game": "black",
        "game_codes": ("IRBO",),
        "rom_versions": (0,),
        "hashes": (),
        "layout": {},
        "parameters": {},
    }
    fields.update(overrides)
    return GameProfile(**fields)


def _shop(shop_id: int, item_ids: tuple[int, ...], archive: str = "arm9") -> Shop:
    return Shop(
        shop_id=shop_id,
        name=f"Shop {shop_id}",
        kind="specialty",
        is_main_game=True,
        item_ids=item_ids,
        provenance=RecordProvenance(source="rom", archive=archive, member=shop_id),
    )


class ShopRecordsTests(unittest.TestCase):
    def test_expands_item_ids_into_named_records_and_drops_the_raw_ids(self) -> None:
        shop = _shop(1, (2, 5))
        item_names = [
            "Potion",
            "Antidote",
            "Burn Heal",
            "Ice Heal",
            "Awakening",
            "Full Heal",
        ]

        records = _shop_records([shop], item_names)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertNotIn("item_ids", record)
        self.assertEqual(record["shop_id"], 1)
        self.assertEqual(
            record["items"],
            [
                {"item_id": 2, "name": "Burn Heal"},
                {"item_id": 5, "name": "Full Heal"},
            ],
        )

    def test_returns_an_empty_list_for_no_shops(self) -> None:
        self.assertEqual(_shop_records([], []), [])


class MartExtractionDispatchTests(unittest.TestCase):
    def test_requires_a_known_profile(self) -> None:
        with self.assertRaises(ProfileError):
            extract_mart_dataset(SimpleNamespace(match=None, image=SimpleNamespace()))

    def test_missing_overlay_metadata_raises_profile_error(self) -> None:
        profile = _profile(layout={}, parameters={})
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile), image=SimpleNamespace()
        )
        with self.assertRaisesRegex(ProfileError, "missing mart metadata"):
            extract_mart_dataset(result)


class OverlayMartExtractionTests(unittest.TestCase):
    """Covers gen5_bw's overlay-based branch (no shop_items/shop_catalog_locator)."""

    def test_extracts_shops_from_a_decompressed_overlay(self) -> None:
        profile = _profile(
            layout={"messages": "messages.narc"},
            parameters={"item_names_member": 3, "shop_item_overlay_id": 7},
        )
        filesystem_data = {"messages.narc": b"MSGBLOB"}
        archive_registry = {b"MSGBLOB": _FakeArchive({3: b"names"}, 4)}
        platform = _fake_platform(
            filesystem_data,
            archive_registry,
            read_overlay_decompressed=lambda image, overlay_id: (
                SimpleNamespace(file_id=77),
                b"OVERLAYDATA",
            ),
        )
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )
        item_names = ("Potion", "Antidote", "Burn Heal", "Ice Heal")
        shops = (_shop(0, (1, 2), archive="overlay7"),)

        with (
            patch(
                "romwiki.pipeline.extraction.marts.get_platform", return_value=platform
            ),
            patch(
                "romwiki.engines.gen5.bw.parse_english_message_archive",
                return_value=item_names,
            ),
            patch(
                "romwiki.engines.gen5.bw.parse_shop_catalog", return_value=shops
            ) as mock_parse_shop_catalog,
        ):
            dataset = extract_mart_dataset(result)

        mock_parse_shop_catalog.assert_called_once_with(
            b"OVERLAYDATA", archive_path="overlay7"
        )
        self.assertEqual(dataset["schema_version"], MARTS_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "marts")
        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(
            dataset["source"]["shop_item_overlay"], {"id": 7, "file_id": 77}
        )
        self.assertEqual(
            dataset["source"]["item_names"],
            {"archive": "messages.narc", "member": 3},
        )
        self.assertEqual(
            dataset["records"][0]["items"],
            [{"item_id": 1, "name": "Antidote"}, {"item_id": 2, "name": "Burn Heal"}],
        )


class Arm9LocatorMartExtractionTests(unittest.TestCase):
    """Covers gen4_hgss's arm9-locator branch (`shop_catalog_locator`)."""

    def test_extracts_shops_using_a_hex_locator_against_arm9(self) -> None:
        profile = _profile(
            engine="gen4_hgss",
            layout={"messages": "messages.narc"},
            parameters={
                "item_names_member": 2,
                "shop_catalog_locator": "aabbcc",
            },
        )
        filesystem_data = {"messages.narc": b"MSGBLOB"}
        archive_registry = {b"MSGBLOB": _FakeArchive({2: b"names"}, 3)}
        platform = _fake_platform(filesystem_data, archive_registry)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )
        item_names = ("Potion", "Antidote")
        shops = (_shop(0, (1,)),)

        with (
            patch(
                "romwiki.pipeline.extraction.marts.get_platform", return_value=platform
            ),
            patch(
                "romwiki.pipeline.extraction.marts.read_code_binary",
                return_value=b"ARM9DATA",
            ),
            patch(
                "romwiki.engines.gen4.hgss.parse_english_message_archive",
                return_value=item_names,
            ),
            patch(
                "romwiki.engines.gen4.hgss.parse_shop_catalog", return_value=shops
            ) as mock_parse_shop_catalog,
        ):
            dataset = extract_mart_dataset(result)

        mock_parse_shop_catalog.assert_called_once_with(
            b"ARM9DATA",
            locator=bytes.fromhex("aabbcc"),
            archive_path="arm9",
            item_count=2,
        )
        self.assertEqual(
            dataset["source"]["shop_catalog"],
            {"archive": "arm9", "locator": "aabbcc"},
        )
        self.assertEqual(
            dataset["records"][0]["items"], [{"item_id": 1, "name": "Antidote"}]
        )

    def test_invalid_hex_locator_raises_profile_error(self) -> None:
        profile = _profile(
            engine="gen4_hgss",
            layout={"messages": "messages.narc"},
            parameters={
                "item_names_member": 2,
                "shop_catalog_locator": "not-hex",
            },
        )
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile), image=SimpleNamespace()
        )
        with self.assertRaisesRegex(ProfileError, "invalid mart metadata"):
            extract_mart_dataset(result)


class ArchiveMartExtractionTests(unittest.TestCase):
    """Covers gen5_b2w2's archive-based branch (`layout.shop_items`)."""

    def test_extracts_shops_from_a_dedicated_archive(self) -> None:
        profile = _profile(
            engine="gen5_b2w2",
            layout={"messages": "messages.narc", "shop_items": "shops.narc"},
            parameters={"item_names_member": 4},
        )
        filesystem_data = {
            "messages.narc": b"MSGBLOB",
            "shops.narc": b"SHOPSBLOB",
        }
        archive_registry = {
            b"MSGBLOB": _FakeArchive({4: b"names"}, 5),
            b"SHOPSBLOB": _FakeArchive({0: b"shop0", 1: b"shop1"}, 2),
        }
        platform = _fake_platform(filesystem_data, archive_registry)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafe")),
        )
        item_names = ("Potion", "Antidote", "Burn Heal")
        shops = (_shop(0, (2,), archive="shops.narc"),)

        with (
            patch(
                "romwiki.pipeline.extraction.marts.get_platform", return_value=platform
            ),
            patch(
                "romwiki.engines.gen5.b2w2.parse_english_message_archive",
                return_value=item_names,
            ),
            patch(
                "romwiki.engines.gen5.b2w2.parse_archive_shop_catalog",
                return_value=shops,
            ) as mock_parse_archive_shop_catalog,
        ):
            dataset = extract_mart_dataset(result)

        mock_parse_archive_shop_catalog.assert_called_once_with(
            (b"shop0", b"shop1"), archive_path="shops.narc"
        )
        self.assertEqual(dataset["source"]["shop_items"], {"archive": "shops.narc"})
        self.assertEqual(
            dataset["records"][0]["items"], [{"item_id": 2, "name": "Burn Heal"}]
        )

    def test_missing_archive_metadata_raises_profile_error(self) -> None:
        profile = _profile(
            engine="gen5_b2w2",
            layout={"shop_items": "shops.narc"},
            parameters={},
        )
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile), image=SimpleNamespace()
        )
        with self.assertRaisesRegex(ProfileError, "missing archive mart metadata"):
            extract_mart_dataset(result)


if __name__ == "__main__":
    unittest.main()
