from __future__ import annotations

import struct
import unittest

from romwiki.platforms.nds.narc import NarcArchive
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_narc


class NarcArchiveTests(unittest.TestCase):
    def test_reads_members_using_allocation_offsets(self) -> None:
        archive = NarcArchive.from_bytes(make_narc())

        self.assertEqual(len(archive.members), 2)
        self.assertEqual(archive.read(0), b"abc")
        self.assertEqual(archive.read(1), b"de")

    def test_rejects_a_member_outside_the_data_block(self) -> None:
        data = bytearray(make_narc())
        struct.pack_into("<I", data, 24, 999)

        with self.assertRaises(InvalidRomError):
            NarcArchive.from_bytes(data)

    def test_can_read_available_part_of_an_explicitly_truncated_last_member(
        self,
    ) -> None:
        data = make_narc()[:-1]

        with self.assertRaises(InvalidRomError):
            NarcArchive.from_bytes(data)

        archive = NarcArchive.from_bytes(data, allow_truncated=True)
        self.assertEqual(archive.read(0), b"abc")
        self.assertEqual(archive.read(1), b"d")

    def test_can_ignore_explicitly_allowed_data_after_the_declared_archive(
        self,
    ) -> None:
        data = make_narc() + b"tool-output"

        with self.assertRaisesRegex(InvalidRomError, "size does not match"):
            NarcArchive.from_bytes(data)

        archive = NarcArchive.from_bytes(data, allow_trailing_data=True)
        self.assertEqual(archive.read(1), b"de")

    def test_can_infer_an_explicitly_allowed_incorrect_data_block_size(self) -> None:
        data = bytearray(make_narc())
        data.extend(b"\0" * 8)
        struct.pack_into("<I", data, 8, len(data))

        with self.assertRaisesRegex(InvalidRomError, "blocks do not fill"):
            NarcArchive.from_bytes(data)

        archive = NarcArchive.from_bytes(
            data, allow_incorrect_data_block_size=True
        )
        self.assertEqual(archive.read(1), b"de")


if __name__ == "__main__":
    unittest.main()
