from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.extraction.egg_moves import extract_egg_move_dataset
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.egg_moves import ArchiveEggMoveSet, OverlayEggMoveSet
from romwiki.schema.pokemon import RecordProvenance
from romwiki.util.errors import ProfileError


def _profile(**overrides) -> GameProfile:
    fields = {
        "id": "test",
        "name": "Test",
        "platform": "nintendo-ds",
        "engine": "gen4_dppt",
        "base_game": "platinum",
        "game_codes": ("CPUE",),
        "rom_versions": (1,),
        "hashes": (),
        "layout": {},
        "parameters": {},
    }
    fields.update(overrides)
    return GameProfile(**fields)


def _result(profile: GameProfile | None) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "romsha256"
    match = (
        HashMatch(
            profile=profile,
            known_hash=KnownHash(algorithm="sha256", value="romsha256", variant="v1"),
        )
        if profile
        else None
    )
    return InspectionResult(image=image, match=match)


def _fake_engine(*, egg_moves_format: str, concern: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        formats=SimpleNamespace(egg_moves=egg_moves_format), egg_moves=concern
    )


def _overlay_set(species_id: int, move_ids=(1, 2)) -> OverlayEggMoveSet:
    return OverlayEggMoveSet(
        species_id=species_id,
        move_ids=move_ids,
        table_index=species_id,
        overlay_offset=0x100 + species_id,
    )


def _archive_set(species_id: int, move_ids=(3, 4, 5)) -> ArchiveEggMoveSet:
    return ArchiveEggMoveSet(
        species_id=species_id,
        move_ids=move_ids,
        provenance=RecordProvenance(
            source="rom", archive="egg.narc", member=species_id
        ),
    )


def _archive(count: int) -> SimpleNamespace:
    return SimpleNamespace(
        members=[SimpleNamespace(index=index) for index in range(count)]
    )


class ExtractEggMoveDatasetDispatchTests(unittest.TestCase):
    def test_raises_profile_error_without_match(self) -> None:
        with self.assertRaises(ProfileError):
            extract_egg_move_dataset(_result(None))

    def test_raises_profile_error_for_unsupported_engine_format(self) -> None:
        profile = _profile()
        engine = _fake_engine(egg_moves_format="none", concern=SimpleNamespace())

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            self.assertRaisesRegex(
                ProfileError, "does not support egg move extraction"
            ),
        ):
            extract_egg_move_dataset(_result(profile))


class ExtractFromOverlayTableTests(unittest.TestCase):
    def test_raises_profile_error_without_overlay_metadata(self) -> None:
        profile = _profile()
        engine = _fake_engine(
            egg_moves_format="overlay-table", concern=SimpleNamespace()
        )

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            self.assertRaisesRegex(ProfileError, "does not define an egg move table"),
        ):
            extract_egg_move_dataset(_result(profile))

    def test_success_builds_envelope_with_move_reference_count(self) -> None:
        profile = _profile(
            parameters={"egg_move_overlay_id": 78, "egg_move_offset": 0x2000}
        )
        overlay = SimpleNamespace(id=78, file_id=140)
        records = (_overlay_set(1, (1, 2)), _overlay_set(2, (3,)))
        parse_egg_move_table = Mock(return_value=records)
        engine = _fake_engine(
            egg_moves_format="overlay-table",
            concern=SimpleNamespace(parse_egg_move_table=parse_egg_move_table),
        )
        platform = SimpleNamespace(
            read_overlay=Mock(return_value=(overlay, b"overlay-data"))
        )

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_platform",
                return_value=platform,
            ),
        ):
            result = extract_egg_move_dataset(_result(profile))

        parse_egg_move_table.assert_called_once_with(
            b"overlay-data", table_offset=0x2000
        )
        self.assertEqual(result["dataset"], "egg_moves")
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(
            result["source"],
            {
                "rom_sha256": "romsha256",
                "overlay_id": 78,
                "overlay_file_id": 140,
                "table_offset": 0x2000,
            },
        )
        self.assertEqual(result["move_reference_count"], 3)
        self.assertEqual(result["records"][0]["species_id"], 1)


class ExtractFromArchiveTableTests(unittest.TestCase):
    def test_raises_profile_error_when_table_archive_has_multiple_members(
        self,
    ) -> None:
        profile = _profile(layout={"egg_moves": "egg.narc"})
        filesystem = Mock()
        filesystem.read.return_value = b"egg-data"
        archive_cls = Mock()
        archive_cls.from_bytes = Mock(return_value=_archive(2))
        platform = SimpleNamespace(
            archive_cls=archive_cls, filesystem_from_image=Mock(return_value=filesystem)
        )
        engine = _fake_engine(
            egg_moves_format="archive-table", concern=SimpleNamespace()
        )

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_platform",
                return_value=platform,
            ),
            self.assertRaisesRegex(
                ProfileError, "egg move table archive must contain one member"
            ),
        ):
            extract_egg_move_dataset(_result(profile))

    def test_success_reads_single_member_table_with_move_reference_count(
        self,
    ) -> None:
        profile = _profile(layout={"egg_moves": "egg.narc"})
        filesystem = Mock()
        filesystem.read.return_value = b"egg-data"
        archive = _archive(1)
        archive.read = Mock(return_value=b"member-0-data")
        archive_cls = Mock()
        archive_cls.from_bytes = Mock(return_value=archive)
        platform = SimpleNamespace(
            archive_cls=archive_cls, filesystem_from_image=Mock(return_value=filesystem)
        )
        records = (_overlay_set(1, (10, 11)),)
        parse_egg_move_table = Mock(return_value=records)
        engine = _fake_engine(
            egg_moves_format="archive-table",
            concern=SimpleNamespace(parse_egg_move_table=parse_egg_move_table),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_platform",
                return_value=platform,
            ),
        ):
            result = extract_egg_move_dataset(_result(profile))

        parse_egg_move_table.assert_called_once_with(b"member-0-data", table_offset=0)
        self.assertEqual(
            result["source"],
            {"rom_sha256": "romsha256", "archive": "egg.narc", "member": 0},
        )
        self.assertEqual(result["move_reference_count"], 2)
        self.assertEqual(result["record_count"], 1)


class ExtractFromSpeciesArchiveTests(unittest.TestCase):
    def test_success_parses_one_record_per_member_with_move_reference_count(
        self,
    ) -> None:
        profile = _profile(layout={"egg_moves": "egg.narc"})
        filesystem = Mock()
        filesystem.read.return_value = b"egg-data"
        archive = _archive(2)
        archive.read = Mock(side_effect=lambda index: f"member-{index}".encode())
        archive_cls = Mock()
        archive_cls.from_bytes = Mock(return_value=archive)
        platform = SimpleNamespace(
            archive_cls=archive_cls, filesystem_from_image=Mock(return_value=filesystem)
        )
        parse_egg_move_set = Mock(
            side_effect=[_archive_set(0, ()), _archive_set(1, (6, 7))]
        )
        engine = _fake_engine(
            egg_moves_format="species-archive",
            concern=SimpleNamespace(parse_egg_move_set=parse_egg_move_set),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_engine",
                return_value=engine,
            ),
            patch(
                "romwiki.pipeline.extraction.egg_moves.get_platform",
                return_value=platform,
            ),
        ):
            result = extract_egg_move_dataset(_result(profile))

        self.assertEqual(parse_egg_move_set.call_count, 2)
        parse_egg_move_set.assert_any_call(
            b"member-0", species_id=0, archive_path="egg.narc"
        )
        parse_egg_move_set.assert_any_call(
            b"member-1", species_id=1, archive_path="egg.narc"
        )
        self.assertEqual(
            result["source"], {"rom_sha256": "romsha256", "archive": "egg.narc"}
        )
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["move_reference_count"], 2)
        self.assertEqual([record["species_id"] for record in result["records"]], [0, 1])


if __name__ == "__main__":
    unittest.main()
