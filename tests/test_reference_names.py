from __future__ import annotations

from unittest.mock import Mock, patch
import unittest

from romwiki.util.errors import DataSourceError
from romwiki.pipeline.reference_names import extract_reference_names
from romwiki.profiles.models import GameProfile


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
            "romwiki.pipeline.reference_names.parse_english_message_archive",
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
        with patch(
            "romwiki.pipeline.reference_names.parse_english_message_archive",
            return_value=("Normal",),
        ):
            with self.assertRaisesRegex(DataSourceError, "exactly 18 names"):
                extract_reference_names(profile, Mock(), archive)


def _profile() -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
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
