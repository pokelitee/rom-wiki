from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from romwiki.engines.registry import (
    EngineAdapter,
    EngineFormats,
    register_engine,
    unregister_engine,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trades import extract_npc_trade_dataset
from romwiki.platforms.nds import NarcMember
from romwiki.platforms.registry import (
    PlatformAdapter,
    register_platform,
    unregister_platform,
)
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.versions import NPC_TRADES_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError

_PLATFORM_ID = "fake-trades-platform"
_ENGINE_ID = "fake_trades_engine"


class _FakeArchive:
    def __init__(self, member_count: int) -> None:
        self.members = tuple(
            NarcMember(index=index, start=0, end=0) for index in range(member_count)
        )

    def read(self, index: int) -> bytes:
        return bytes([index])


def _register_fake_platform(
    trades_archive: _FakeArchive, messages_archive: Mock
) -> None:
    archive_cls = Mock()
    archive_cls.from_bytes.side_effect = [trades_archive, messages_archive]
    register_platform(
        _PLATFORM_ID,
        PlatformAdapter(
            inspect=lambda path: None,
            filesystem_from_image=lambda image: Mock(read=Mock(return_value=b"raw")),
            matches_header=lambda image, codes, versions: True,
            archive_cls=archive_cls,
        ),
    )


def _register_fake_engine(trades: SimpleNamespace) -> None:
    fields = dict.fromkeys(EngineAdapter.__dataclass_fields__, SimpleNamespace())
    fields["trades"] = trades
    fields["generation"] = None
    fields["dataset_kinds"] = frozenset({"pokemon"})
    fields["required_dataset_kinds"] = frozenset({"pokemon"})
    fields["formats"] = EngineFormats(
        encounters="unsupported",
        locations="unsupported",
        location_extraction="unsupported",
        pickup="none",
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
    defaults = {
        "id": "test-trades",
        "name": "Test Trades",
        "platform": _PLATFORM_ID,
        "engine": _ENGINE_ID,
        "base_game": "test",
        "game_codes": (),
        "rom_versions": (),
        "hashes": (KnownHash(algorithm="sha256", value="abc123", variant="retail"),),
        "layout": {"npc_trades": "trades.narc", "messages": "messages.narc"},
        "parameters": {"npc_trade_names_member": 2},
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


def _parse_npc_trade_record(
    data: bytes, *, trade_id: int, nickname: str, ot_name: str, archive_path: str
):
    return SimpleNamespace(
        to_dict=lambda: {
            "trade_id": trade_id,
            "nickname": nickname,
            "ot_name": ot_name,
            "interaction": "default",
        }
    )


class ExtractNpcTradeDatasetTests(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_platform(_PLATFORM_ID)
        unregister_engine(_ENGINE_ID)

    def test_raises_without_a_matched_profile(self) -> None:
        with self.assertRaisesRegex(
            ProfileError, "known game profile is required for trade"
        ):
            extract_npc_trade_dataset(_result(None))

    def test_raises_when_trade_metadata_is_missing(self) -> None:
        profile = _profile(parameters={})
        _register_fake_platform(_FakeArchive(1), Mock())
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(),
                parse_npc_trade_record=_parse_npc_trade_record,
            )
        )

        with self.assertRaisesRegex(ProfileError, "is missing NPC trade metadata"):
            extract_npc_trade_dataset(_result(profile))

    def test_extracts_a_nickname_and_ot_name_per_trade(self) -> None:
        profile = _profile()
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        _register_fake_platform(_FakeArchive(2), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(
                    return_value=("Nick1", "OT1", "Nick2", "OT2")
                ),
                parse_npc_trade_record=_parse_npc_trade_record,
            )
        )

        dataset = extract_npc_trade_dataset(_result(profile))

        self.assertEqual(dataset["schema_version"], NPC_TRADES_RAW_SCHEMA_VERSION)
        self.assertEqual(dataset["dataset"], "trades")
        self.assertEqual(dataset["record_count"], 2)
        self.assertEqual(dataset["records"][0]["nickname"], "Nick1")
        self.assertEqual(dataset["records"][0]["ot_name"], "OT1")
        self.assertEqual(dataset["records"][1]["nickname"], "Nick2")
        self.assertEqual(dataset["records"][1]["ot_name"], "OT2")
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "abc123",
                "archive": "trades.narc",
                "trade_names": {"archive": "messages.narc", "member": 2},
            },
        )

    def test_skips_configured_unused_trades(self) -> None:
        profile = _profile(
            parameters={"npc_trade_names_member": 2, "npc_trades_unused": (1,)}
        )
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        _register_fake_platform(_FakeArchive(2), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(
                    return_value=("Nick1", "OT1", "Nick2", "OT2")
                ),
                parse_npc_trade_record=_parse_npc_trade_record,
            )
        )

        dataset = extract_npc_trade_dataset(_result(profile))

        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(dataset["records"][0]["nickname"], "Nick1")

    def test_overrides_interaction_using_the_engine_lookup_table(self) -> None:
        profile = _profile()
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        _register_fake_platform(_FakeArchive(1), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(return_value=("Nick1", "OT1")),
                parse_npc_trade_record=_parse_npc_trade_record,
                NPC_TRADE_INTERACTION_BY_ID={0: "give-and-take"},
            )
        )

        dataset = extract_npc_trade_dataset(_result(profile))

        self.assertEqual(dataset["records"][0]["interaction"], "give-and-take")

    def test_raises_when_trade_name_bank_size_is_wrong(self) -> None:
        profile = _profile()
        messages_archive = Mock()
        messages_archive.read.return_value = b"raw"
        _register_fake_platform(_FakeArchive(2), messages_archive)
        _register_fake_engine(
            SimpleNamespace(
                parse_english_message_archive=Mock(
                    return_value=("Nick1", "OT1", "Nick2")
                ),
                parse_npc_trade_record=_parse_npc_trade_record,
            )
        )

        with self.assertRaisesRegex(
            InvalidRomError, "one nickname and OT name per trade"
        ):
            extract_npc_trade_dataset(_result(profile))


if __name__ == "__main__":
    unittest.main()
