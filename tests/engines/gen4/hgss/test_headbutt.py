from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.headbutt import parse_headbutt_record
from romwiki.util.errors import InvalidRomError


def _record(regular: int = 1, secret: int = 1) -> bytes:
    slots = b"".join(
        struct.pack("<HBB", 10 + index, 5 + index, 8 + index) for index in range(18)
    )
    coordinates = b"".join(
        struct.pack("<2h", index, -index) for index in range((regular + secret) * 6)
    )
    return struct.pack("<2H", regular, secret) + slots + coordinates


class HeadbuttRecordTests(unittest.TestCase):
    def test_parses_pools_tree_groups_and_coordinates(self) -> None:
        record = parse_headbutt_record(
            _record(),
            header_id=9,
            archive_path="a/2/5/2",
            species_count=500,
        )

        assert record is not None
        self.assertEqual(
            [slot.chance for slot in record.pools["common"]], [50, 15, 15, 10, 5, 5]
        )
        self.assertEqual(record.pools["secret"][5].species_id, 27)
        self.assertEqual(
            [group.kind for group in record.tree_groups], ["regular", "secret"]
        )
        self.assertEqual(record.tree_groups[1].coordinates[0], (6, -6))

    def test_accepts_only_exact_empty_or_populated_sizes(self) -> None:
        self.assertIsNone(
            parse_headbutt_record(
                b"\0\0\0\0",
                header_id=0,
                archive_path="a/2/5/2",
                species_count=500,
            )
        )
        with self.assertRaisesRegex(InvalidRomError, "expected"):
            parse_headbutt_record(
                _record()[:-1],
                header_id=9,
                archive_path="a/2/5/2",
                species_count=500,
            )

    def test_validates_and_removes_coordinate_terminator_padding(self) -> None:
        data = bytearray(_record())
        coordinate_offset = 4 + 18 * 4
        for index in range(1, 6):
            struct.pack_into("<2h", data, coordinate_offset + index * 4, -1, -1)

        record = parse_headbutt_record(
            bytes(data),
            header_id=9,
            archive_path="a/2/5/2",
            species_count=500,
        )

        assert record is not None
        self.assertEqual(record.tree_groups[0].coordinates, ((0, 0),))
        struct.pack_into("<2h", data, coordinate_offset + 3 * 4, 4, 5)
        with self.assertRaisesRegex(InvalidRomError, "after its terminator"):
            parse_headbutt_record(
                bytes(data),
                header_id=9,
                archive_path="a/2/5/2",
                species_count=500,
            )
