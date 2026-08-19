from __future__ import annotations

import unittest
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import patch

from romwiki.engines.gen4.dppt import Gen4BerryData, Gen4FossilRevival
from romwiki.pipeline.extraction.items import extract_item_dataset
from romwiki.profiles.models import GameProfile
from romwiki.schema import Item, RecordProvenance
from romwiki.schema.versions import ITEMS_RAW_SCHEMA_VERSION
from romwiki.util.errors import DataSourceError, ProfileError
from romwiki.util.text import name_slug


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
    filesystem_data: dict[str, bytes], archive_registry: dict[bytes, _FakeArchive]
) -> SimpleNamespace:
    return SimpleNamespace(
        filesystem_from_image=lambda image: _FakeFilesystem(filesystem_data),
        archive_cls=_FakeArchiveCls(archive_registry),
        read_code_binary=lambda image: b"ARM9DATA",
        read_decompressed_code_binary=lambda image: b"ARM9DATA",
    )


def _profile(**overrides: object) -> GameProfile:
    fields = {
        "id": "test",
        "name": "Test",
        "platform": "nintendo-ds",
        "engine": "gen4_dppt",
        "base_game": "platinum",
        "game_codes": ("CPUE",),
        "rom_versions": (1,),
        "hashes": (),
        "layout": {
            "item_data": "items.narc",
            "messages": "messages.narc",
            "berry_data": "berries.narc",
        },
        "parameters": {
            "item_names_member": 1,
            "type_names_member": 2,
            "fossil_revival_table_offset": 10,
            "fossil_revival_count": 1,
            "first_berry_item_id": 1,
        },
    }
    fields.update(overrides)
    return GameProfile(**fields)  # type: ignore[arg-type]


def _item(item_id: int, data_member: int, **overrides: object) -> Item:
    fields = {
        "item_id": item_id,
        "data_archive_member": data_member,
        "price": 100,
        "hold_effect_id": 0,
        "hold_effect_parameter": None,
        "pluck_effect_id": 0,
        "fling_effect_id": 0,
        "fling_power": 0,
        "natural_gift_power": 0,
        "natural_gift_type_id": 31,
        "prevent_toss": False,
        "selectable": False,
        "field_pocket_id": 0,
        "battle_pocket_mask": 0,
        "field_use_function_id": 0,
        "battle_use_function_id": 0,
        "party_use": False,
        "party_effects": None,
        "provenance": RecordProvenance(
            source="rom", archive="items.narc", member=data_member
        ),
    }
    fields.update(overrides)
    return Item(**fields)  # type: ignore[arg-type]


class ItemExtractionTests(unittest.TestCase):
    def test_requires_a_known_profile(self) -> None:
        with self.assertRaises(ProfileError):
            extract_item_dataset(SimpleNamespace(match=None, image=SimpleNamespace()))

    def test_missing_required_layout_key_raises_profile_error(self) -> None:
        profile = _profile(layout={"messages": "messages.narc"})
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile), image=SimpleNamespace()
        )
        with self.assertRaisesRegex(ProfileError, "item_data"):
            extract_item_dataset(result)

    def test_extracts_arm9_map_items_with_fossil_and_berry_data(self) -> None:
        profile = _profile()
        filesystem_data = {
            "items.narc": b"ITEMSBLOB",
            "messages.narc": b"MSGBLOB",
            "berries.narc": b"BERRYBLOB",
        }
        archive_registry = {
            b"ITEMSBLOB": _FakeArchive({0: b"i0", 1: b"i1", 2: b"i2"}, 3),
            b"MSGBLOB": _FakeArchive({1: b"names", 2: b"types"}, 3),
            b"BERRYBLOB": _FakeArchive({0: b"berry0"}, 1),
        }
        platform = _fake_platform(filesystem_data, archive_registry)

        item_names = ("???", "Potion", "Antidote")
        type_names = tuple(f"Type{index}" for index in range(18))
        items = [
            _item(0, 0),
            _item(
                1,
                1,
                field_pocket_id=2,
                field_use_function_id=1,
                natural_gift_type_id=5,
            ),
            _item(2, 2, field_pocket_id=7, field_use_function_id=24),
        ]
        fossil_revivals = (Gen4FossilRevival(item_id=1, species_id=138),)
        berry = Gen4BerryData(
            size=2000,
            firmness=3,
            base_yield=5,
            stage_duration=1,
            moisture_drain_rate=1,
            spiciness=10,
            dryness=10,
            sweetness=10,
            bitterness=10,
            sourness=10,
            smoothness=10,
        )

        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="deadbeef")),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.items.get_platform", return_value=platform
            ),
            patch(
                "romwiki.pipeline.extraction.items.extract_reference_descriptions",
                return_value={"item_descriptions": [], "description_sources": {}},
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_english_message_archive",
                side_effect=[item_names, type_names],
            ),
            patch(
                "romwiki.engines.gen4.dppt.find_item_archive_members",
                return_value=(500, (0, 1, 2)),
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_fossil_revival_table",
                return_value=fossil_revivals,
            ),
            patch("romwiki.engines.gen4.dppt.parse_berry_record", return_value=berry),
            patch("romwiki.engines.gen4.dppt.parse_item_record", side_effect=items),
        ):
            dataset = extract_item_dataset(result)

        self.assertEqual(dataset["schema_version"], ITEMS_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "items")
        self.assertEqual(dataset["record_count"], 3)
        self.assertEqual(
            dataset["source"]["item_archive_map"],
            {"source": "arm9", "offset": 500, "record_count": 3},
        )
        self.assertEqual(
            dataset["source"]["fossil_revival_table"],
            {"source": "arm9", "offset": 10, "record_count": 1},
        )
        self.assertEqual(
            dataset["source"]["berry_data"],
            {"archive": "berries.narc", "record_count": 1},
        )

        records = dataset["records"]
        self.assertFalse(records[0]["public"])
        self.assertIsNone(records[0]["revives_into_species_id"])
        self.assertIsNone(records[0]["berry"])

        self.assertTrue(records[1]["public"])
        self.assertEqual(records[1]["revives_into_species_id"], 138)
        self.assertEqual(records[1]["pocket"], {"id": 2, "name": "poke-balls"})
        self.assertEqual(records[1]["field_use"], {"id": 1, "name": "healing"})
        self.assertEqual(
            records[1]["natural_gift_type"],
            {"id": 5, "name": name_slug(type_names[5])},
        )
        self.assertEqual(
            records[1]["berry"],
            {**asdict(berry), "firmness_name": "Hard"},
        )

        self.assertTrue(records[2]["public"])
        self.assertIsNone(records[2]["natural_gift_type"])
        self.assertEqual(dataset["public_record_count"], 2)

    def test_type_names_member_none_uses_engine_fallback_and_omits_source_entry(
        self,
    ) -> None:
        profile = _profile(
            layout={"item_data": "items.narc", "messages": "messages.narc"}
        )
        profile = replace(profile, parameters={**profile.parameters})
        del profile.parameters["type_names_member"]  # type: ignore[attr-defined]
        del profile.parameters["fossil_revival_table_offset"]  # type: ignore[attr-defined]

        filesystem_data = {
            "items.narc": b"ITEMSBLOB",
            "messages.narc": b"MSGBLOB",
        }
        archive_registry = {
            b"ITEMSBLOB": _FakeArchive({0: b"i0"}, 1),
            b"MSGBLOB": _FakeArchive({1: b"names"}, 2),
        }
        platform = _fake_platform(filesystem_data, archive_registry)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="deadbeef")),
        )
        item = _item(0, 0, natural_gift_type_id=0)

        with (
            patch(
                "romwiki.pipeline.extraction.items.get_platform", return_value=platform
            ),
            patch(
                "romwiki.pipeline.extraction.items.extract_reference_descriptions",
                return_value={},
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_english_message_archive",
                return_value=("Potion",),
            ),
            patch(
                "romwiki.engines.gen4.dppt.find_item_archive_members",
                return_value=(0, (0,)),
            ),
            patch("romwiki.engines.gen4.dppt.parse_item_record", return_value=item),
        ):
            dataset = extract_item_dataset(result)

        self.assertNotIn("type_names", dataset["source"])
        from romwiki.engines.gen4.dppt import TYPE_NAMES

        self.assertEqual(
            dataset["records"][0]["natural_gift_type"],
            {"id": 0, "name": name_slug(TYPE_NAMES[0])},
        )

    def test_unknown_item_pocket_raises_data_source_error(self) -> None:
        dataset_kwargs = self._minimal_single_item_setup(
            _item(0, 0, field_pocket_id=99)
        )
        with self.assertRaisesRegex(DataSourceError, "Unknown item pocket ID"):
            extract_item_dataset(dataset_kwargs)

    def test_unknown_field_use_function_raises_data_source_error(self) -> None:
        dataset_kwargs = self._minimal_single_item_setup(
            _item(0, 0, field_use_function_id=99)
        )
        with self.assertRaisesRegex(DataSourceError, "Unknown item field-use"):
            extract_item_dataset(dataset_kwargs)

    def test_unknown_natural_gift_type_raises_data_source_error(self) -> None:
        # 18 mocked type names are configured (indices 0-17); 18 is
        # out-of-range without colliding with NATURAL_GIFT_TYPE_NONE (31).
        dataset_kwargs = self._minimal_single_item_setup(
            _item(0, 0, natural_gift_type_id=18)
        )
        with self.assertRaisesRegex(DataSourceError, "Unknown Natural Gift type"):
            extract_item_dataset(dataset_kwargs)

    def _minimal_single_item_setup(self, item: Item):
        profile = _profile(
            layout={"item_data": "items.narc", "messages": "messages.narc"},
            parameters={"item_names_member": 1, "type_names_member": 2},
        )
        filesystem_data = {
            "items.narc": b"ITEMSBLOB",
            "messages.narc": b"MSGBLOB",
        }
        archive_registry = {
            b"ITEMSBLOB": _FakeArchive({0: b"i0"}, 1),
            b"MSGBLOB": _FakeArchive({1: b"names", 2: b"types"}, 3),
        }
        platform = _fake_platform(filesystem_data, archive_registry)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="deadbeef")),
        )
        self._patches = [
            patch(
                "romwiki.pipeline.extraction.items.get_platform", return_value=platform
            ),
            patch(
                "romwiki.pipeline.extraction.items.extract_reference_descriptions",
                return_value={},
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_english_message_archive",
                side_effect=[("Potion",), tuple(f"Type{i}" for i in range(18))],
            ),
            patch(
                "romwiki.engines.gen4.dppt.find_item_archive_members",
                return_value=(0, (0,)),
            ),
            patch("romwiki.engines.gen4.dppt.parse_item_record", return_value=item),
        ]
        for started in self._patches:
            started.start()
        self.addCleanup(lambda: [started.stop() for started in self._patches])
        return result

    def test_extracts_archive_index_items_with_script_pattern_fossils(self) -> None:
        profile = _profile(
            engine="gen5_bw",
            layout={
                "item_data": "items.narc",
                "messages": "messages.narc",
                "scripts": "scripts.narc",
            },
            parameters={"item_names_member": 5},
        )
        filesystem_data = {
            "items.narc": b"ITEMSBLOB",
            "messages.narc": b"MSGBLOB",
            "scripts.narc": b"SCRIPTSBLOB",
        }
        archive_registry = {
            b"ITEMSBLOB": _FakeArchive({0: b"i0", 1: b"i1"}, 2),
            b"MSGBLOB": _FakeArchive({5: b"names"}, 6),
            b"SCRIPTSBLOB": _FakeArchive({}, 5),
        }
        platform = _fake_platform(filesystem_data, archive_registry)
        result = SimpleNamespace(
            match=SimpleNamespace(profile=profile),
            image=SimpleNamespace(hashes=SimpleNamespace(sha256="cafef00d")),
        )
        item_names = ("Potion", "Antidote")
        gen5_items = [
            Item(
                item_id=0,
                data_archive_member=0,
                price=100,
                hold_effect_id=0,
                hold_effect_parameter=None,
                pluck_effect_id=0,
                fling_effect_id=0,
                fling_power=0,
                natural_gift_power=0,
                natural_gift_type_id=0x1F,
                prevent_toss=False,
                selectable=False,
                field_pocket_id=0,
                battle_pocket_mask=0,
                field_use_function_id=1,
                battle_use_function_id=0,
                party_use=False,
                party_effects=None,
                provenance=RecordProvenance(
                    source="rom", archive="items.narc", member=0
                ),
            ),
            Item(
                item_id=1,
                data_archive_member=1,
                price=200,
                hold_effect_id=0,
                hold_effect_parameter=None,
                pluck_effect_id=0,
                fling_effect_id=0,
                fling_power=0,
                natural_gift_power=0,
                natural_gift_type_id=0x1F,
                prevent_toss=False,
                selectable=False,
                field_pocket_id=4,
                battle_pocket_mask=0,
                field_use_function_id=25,
                battle_use_function_id=0,
                party_use=False,
                party_effects=None,
                provenance=RecordProvenance(
                    source="rom", archive="items.narc", member=1
                ),
            ),
        ]

        with (
            patch(
                "romwiki.pipeline.extraction.items.get_platform", return_value=platform
            ),
            patch(
                "romwiki.pipeline.extraction.items.extract_reference_descriptions",
                return_value={},
            ),
            patch(
                "romwiki.engines.gen5.bw.parse_english_message_archive",
                return_value=item_names,
            ),
            patch(
                "romwiki.engines.gen5.bw.find_fossil_revival_script",
                return_value=(
                    3,
                    (SimpleNamespace(item_id=1, species_id=138),),
                ),
            ),
            patch("romwiki.engines.gen5.bw.parse_item_record", side_effect=gen5_items),
        ):
            dataset = extract_item_dataset(result)

        self.assertEqual(
            dataset["source"]["item_archive_map"],
            {"source": "archive-index", "record_count": 2},
        )
        self.assertEqual(
            dataset["source"]["fossil_revival_table"],
            {
                "source": "script",
                "archive": "scripts.narc",
                "member": 3,
                "record_count": 1,
            },
        )
        self.assertNotIn("type_names", dataset["source"])
        self.assertEqual(dataset["records"][1]["revives_into_species_id"], 138)
        self.assertEqual(
            dataset["records"][1]["pocket"], {"id": 4, "name": "key-items"}
        )
        self.assertEqual(
            dataset["records"][1]["field_use"], {"id": 25, "name": "dowsing-machine"}
        )


if __name__ == "__main__":
    unittest.main()
