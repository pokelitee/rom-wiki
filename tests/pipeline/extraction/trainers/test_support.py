from __future__ import annotations

import unittest
from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from romwiki.pipeline.extraction.trainers.support import (
    read_rematch_table,
    read_starter_branch_families,
    read_starter_species,
)
from romwiki.profiles.models import GameProfile


class ReadStarterBranchFamiliesTests(unittest.TestCase):
    def test_returns_none_without_a_scripts_archive_path(self) -> None:
        profile = _profile(layout={})
        engine = SimpleNamespace(parse_starter_branch_families=Mock())

        result = read_starter_branch_families(
            profile, Mock(), engine, Mock(), trainer_count=5, starter_species=(1, 2)
        )

        self.assertIsNone(result)

    def test_returns_none_without_starter_species(self) -> None:
        profile = _profile(layout={"scripts": "scripts.narc"})
        engine = SimpleNamespace(parse_starter_branch_families=Mock())

        result = read_starter_branch_families(
            profile, Mock(), engine, Mock(), trainer_count=5, starter_species=None
        )

        self.assertIsNone(result)

    def test_decodes_families_from_every_script_member_and_honours_tolerance_flags(
        self,
    ) -> None:
        profile = _profile(
            layout={"scripts": "scripts.narc"},
            parameters={
                "field_archives_allow_incorrect_data_block_size": True,
                "scripts_allow_trailing_data": True,
            },
        )
        members = [SimpleNamespace(index=0), SimpleNamespace(index=1)]
        script_archive = SimpleNamespace(
            members=members,
            read=Mock(side_effect=lambda index: f"script-{index}".encode()),
        )
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = script_archive
        platform = SimpleNamespace(archive_cls=archive_cls)
        filesystem = Mock()
        filesystem.read.return_value = b"raw-scripts"
        parse = Mock(side_effect=[("family-0",), ("family-1", "family-1b")])
        engine = SimpleNamespace(parse_starter_branch_families=parse)

        result = read_starter_branch_families(
            profile,
            platform,
            engine,
            filesystem,
            trainer_count=5,
            starter_species=(1, 2, 3),
        )

        self.assertEqual(result, ("family-0", "family-1", "family-1b"))
        archive_cls.from_bytes.assert_called_once_with(
            b"raw-scripts",
            allow_truncated=True,
            allow_incorrect_data_block_size=True,
            allow_trailing_data=True,
        )
        self.assertEqual(parse.call_count, 2)
        parse.assert_any_call(
            b"script-0",
            script_file_id=0,
            trainer_count=5,
            starter_species=(1, 2, 3),
        )
        parse.assert_any_call(
            b"script-1",
            script_file_id=1,
            trainer_count=5,
            starter_species=(1, 2, 3),
        )


class ReadStarterSpeciesTests(unittest.TestCase):
    def test_returns_none_when_not_configured(self) -> None:
        profile = _profile(parameters={})
        engine = SimpleNamespace(parse_starter_species=Mock())

        result = read_starter_species(profile, Mock(), engine, Mock())

        self.assertIsNone(result)

    def test_prefers_the_decompressing_overlay_reader_when_available(self) -> None:
        profile = _profile(
            parameters={
                "starter_species_overlay_id": 3,
                "starter_species_offset": 16,
                "starter_species_count": 3,
            }
        )
        overlay_bytes = bytes(range(64))
        read_overlay_decompressed = Mock(return_value=(3, overlay_bytes))
        read_overlay = Mock(return_value=(3, overlay_bytes))
        platform = SimpleNamespace(
            read_overlay_decompressed=read_overlay_decompressed,
            read_overlay=read_overlay,
        )
        parse = Mock(return_value=(1, 4, 7))
        engine = SimpleNamespace(
            parse_starter_species=parse,
            STARTER_SPECIES_ENTRY_SIZE=2,
            BASE_SPECIES_COUNT=493,
        )
        image = Mock()

        result = read_starter_species(profile, platform, engine, Mock(image=image))

        self.assertEqual(result, (1, 4, 7))
        read_overlay_decompressed.assert_called_once()
        read_overlay.assert_not_called()
        parse.assert_called_once_with(
            overlay_bytes[16 : 16 + 6], count=3, species_count=494
        )

    def test_falls_back_to_the_raw_overlay_reader(self) -> None:
        profile = _profile(
            parameters={
                "starter_species_overlay_id": 3,
                "starter_species_offset": 0,
                "starter_species_count": 2,
            }
        )
        overlay_bytes = bytes(range(32))
        read_overlay = Mock(return_value=(3, overlay_bytes))
        platform = SimpleNamespace(
            read_overlay_decompressed=None, read_overlay=read_overlay
        )
        parse = Mock(return_value=(1, 2))
        engine = SimpleNamespace(
            parse_starter_species=parse,
            STARTER_SPECIES_ENTRY_SIZE=2,
            BASE_SPECIES_COUNT=493,
        )

        result = read_starter_species(profile, platform, engine, Mock())

        self.assertEqual(result, (1, 2))
        read_overlay.assert_called_once()


class ReadRematchTableTests(unittest.TestCase):
    def test_returns_none_pair_when_not_configured(self) -> None:
        profile = _profile(parameters={})
        engine = SimpleNamespace(parse_rematch_table=Mock())

        source, chains = read_rematch_table(
            profile, Mock(), engine, Mock(), trainer_count=5
        )

        self.assertIsNone(source)
        self.assertIsNone(chains)

    def test_returns_none_pair_when_the_engine_has_no_rematch_table(self) -> None:
        profile = _profile(parameters=_REMATCH_PARAMETERS)
        parse = Mock()
        engine = SimpleNamespace(parse_rematch_table=parse, REMATCH_RECORD_SIZE=8)

        source, chains = read_rematch_table(
            profile, Mock(), engine, Mock(), trainer_count=5
        )

        self.assertEqual((source, chains), (None, None))
        parse.assert_not_called()

    def test_decodes_the_rematch_table_from_the_configured_overlay(self) -> None:
        profile = replace(
            _profile(parameters=_REMATCH_PARAMETERS), engine="gen4_platinum"
        )
        overlay_bytes = bytes(range(64))
        platform = SimpleNamespace(read_overlay=Mock(return_value=(7, overlay_bytes)))
        parse = Mock(return_value=("chain-a", "chain-b"))
        engine = SimpleNamespace(parse_rematch_table=parse, REMATCH_RECORD_SIZE=8)

        source, chains = read_rematch_table(
            profile, platform, engine, Mock(), trainer_count=9
        )

        self.assertEqual(source, {"overlay_id": 7, "offset": 4, "count": 2})
        self.assertEqual(chains, ("chain-a", "chain-b"))
        parse.assert_called_once_with(overlay_bytes[4:20], count=2, trainer_count=9)


_REMATCH_PARAMETERS = {
    "trainer_rematch_overlay_id": 7,
    "trainer_rematch_offset": 4,
    "trainer_rematch_count": 2,
}


def _profile(
    *,
    layout: dict[str, str] | None = None,
    parameters: Mapping[str, object] | None = None,
) -> GameProfile:
    base = GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen5_bw",
        base_game="black",
        game_codes=("IRBO",),
        rom_versions=(0,),
        hashes=(),
        layout={},
        parameters={},
    )
    return replace(
        base,
        layout=layout if layout is not None else {},
        parameters=parameters if parameters is not None else {},
    )


if __name__ == "__main__":
    unittest.main()
