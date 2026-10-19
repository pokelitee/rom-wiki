from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from romwiki.pipeline.extraction.counts import (
    leading_record_count,
    personal_archive_count,
    profile_count,
)
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import ProfileError


class _Archive:
    def __init__(self, sizes: list[int]) -> None:
        self._sizes = sizes
        self.members = [SimpleNamespace(index=index) for index in range(len(sizes))]

    @classmethod
    def from_bytes(cls, data: bytes) -> _Archive:
        return cls(list(data))

    def read(self, index: int) -> bytes:
        return bytes(self._sizes[index])


def _profile(**parameters: object) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine="gen5_bw",
        base_game="black",
        game_codes=(),
        rom_versions=(),
        hashes=(),
        layout={"personal": "personal.narc"},
        parameters=dict(parameters),
    )


class RecordCountTests(unittest.TestCase):
    def test_counts_records_up_to_a_larger_trailing_member(self) -> None:
        # Generation V appends a non-record table; a placeholder record may
        # also be shorter than the rest.
        archive = _Archive([56, 60, 60, 1300, 60])

        self.assertEqual(leading_record_count(archive, 60), 3)

    def test_counts_every_member_of_an_archive_of_records(self) -> None:
        self.assertEqual(leading_record_count(_Archive([44] * 5), 44), 5)

    def test_reads_the_personal_archive_with_the_engines_record_size(self) -> None:
        filesystem = Mock()
        filesystem.read.return_value = bytes([60, 60, 200])
        platform = SimpleNamespace(archive_cls=_Archive)

        count = personal_archive_count(_profile(), platform, filesystem)

        filesystem.read.assert_called_once_with("personal.narc")
        self.assertEqual(count, 2)

    def test_a_profile_may_resize_a_table(self) -> None:
        self.assertEqual(profile_count(_profile(), "move_name_count", 560), 560)
        self.assertEqual(
            profile_count(_profile(move_name_count=600), "move_name_count", 560), 600
        )

    def test_rejects_a_negative_table_size(self) -> None:
        with self.assertRaisesRegex(ProfileError, "move_name_count"):
            profile_count(_profile(move_name_count=-1), "move_name_count", 560)


if __name__ == "__main__":
    unittest.main()
