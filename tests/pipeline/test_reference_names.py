from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import DataSourceError


class ReferenceNameTests(unittest.TestCase):
    def test_extracts_configured_rom_name_tables_with_provenance(self) -> None:
        profile = _profile()
        archive = Mock()
        archive.read.side_effect = [b"types", b"abilities", b"items", b"moves"]
        type_names = tuple(f"Type {index}" for index in range(18))
        ability_names = tuple(f"Ability {index}" for index in range(124))
        item_names = tuple(f"Item {index}" for index in range(468))
        move_names = tuple(f"Move {index}" for index in range(468))

        with patch(
            "romwiki.engines.gen4.dppt.parse_english_message_archive",
            side_effect=[type_names, ability_names, item_names, move_names],
        ):
            result = extract_reference_names(profile, Mock(), archive)

        self.assertEqual(result["type_names"], list(type_names))
        self.assertEqual(result["ability_names"], list(ability_names))
        self.assertEqual(result["item_names"], list(item_names))
        self.assertEqual(result["move_names"], list(move_names))
        self.assertEqual(
            result["name_sources"]["move_names"],
            {"archive": "messages.narc", "member": 647},
        )

    def test_rejects_an_unexpected_name_count(self) -> None:
        profile = _profile()
        archive = Mock()
        with (
            patch(
                "romwiki.engines.gen4.dppt.parse_english_message_archive",
                return_value=("Normal",),
            ),
            self.assertRaisesRegex(DataSourceError, "exactly 18 names"),
        ):
            extract_reference_names(profile, Mock(), archive)

    def test_allows_an_explicitly_truncated_message_archive(self) -> None:
        profile = _profile()
        profile.parameters.clear()
        profile.parameters.update(
            {"ability_names_member": 610, "messages_allow_truncated": True}
        )
        filesystem = Mock()
        filesystem.read.return_value = b"archive"
        archive = Mock()
        archive.read.return_value = b"abilities"
        archive_cls = Mock()
        archive_cls.from_bytes.return_value = archive
        names = tuple(f"Ability {index}" for index in range(124))

        with (
            patch(
                "romwiki.pipeline.reference_names.get_platform",
                return_value=SimpleNamespace(archive_cls=archive_cls),
            ),
            patch(
                "romwiki.engines.gen4.dppt.parse_english_message_archive",
                return_value=names,
            ),
        ):
            result = extract_reference_names(profile, filesystem)

        archive_cls.from_bytes.assert_called_once_with(b"archive", allow_truncated=True)
        self.assertEqual(result["ability_names"], list(names))


def _profile() -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen4_dppt",
        base_game="platinum",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
        layout={"messages": "messages.narc"},
        parameters={
            "type_names_member": 624,
            "ability_names_member": 610,
            "item_names_member": 392,
            "move_names_member": 647,
        },
    )


if __name__ == "__main__":
    unittest.main()
