from __future__ import annotations

import struct
import unittest
from collections.abc import Callable

from romwiki.engines.gen3.shared.locations import (
    count_map_groups,
    parse_gmapgroups_pointers,
    parse_map_group_index,
    parse_map_header,
    parse_map_header_table,
)

_GROUP_COUNT = 43
from romwiki.schema import EncounterMapLocation
from romwiki.util.errors import InvalidRomError


def _header(
    *, music: int = 273, map_layout_id: int = 1, region_map_section_id: int = 88
) -> bytes:
    data = bytearray(28)
    struct.pack_into("<HH", data, 0x10, music, map_layout_id)
    data[0x14] = region_map_section_id
    return bytes(data)


class ParseMapHeaderTests(unittest.TestCase):
    def test_decodes_music_layout_and_region(self) -> None:
        header = _header(music=300, map_layout_id=42, region_map_section_id=90)

        music, map_layout_id, region_map_section_id = parse_map_header(
            header, header_id=0
        )

        self.assertEqual(music, 300)
        self.assertEqual(map_layout_id, 42)
        self.assertEqual(region_map_section_id, 90)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_header(b"\x00" * 10, header_id=0)


class ParseMapHeaderTableTests(unittest.TestCase):
    def test_decodes_records_with_section_names(self) -> None:
        region_names = {88: "PALLET TOWN", 89: "VIRIDIAN CITY"}
        header_data = _header(region_map_section_id=89) + _header(
            region_map_section_id=88
        )

        records = parse_map_header_table(
            header_data,
            region_names,
            header_ids=[0, 2],
            archive_path="gMapGroups:0x3526a8",
        )

        self.assertEqual(len(records), 2)
        self.assertIsInstance(records[0], EncounterMapLocation)
        self.assertEqual(records[0].header_id, 0)
        self.assertEqual(records[0].name, "VIRIDIAN CITY")
        self.assertEqual(records[1].name, "PALLET TOWN")
        self.assertEqual(records[0].matrix_id, 0)
        self.assertEqual(records[0].encounter_map_index, None)
        self.assertEqual(records[1].header_id, 2)
        self.assertEqual(records[0].provenance.archive, "gMapGroups:0x3526a8")
        self.assertEqual(records[0].provenance.member, 0)
        self.assertEqual(records[1].provenance.member, 2)

    def test_rejects_wrong_header_data_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_map_header_table(
                b"\x00" * 10, {88: "PALLET TOWN"}, header_ids=[0, 1], archive_path="0x0"
            )

    def test_rejects_a_section_without_a_name(self) -> None:
        header_data = _header(region_map_section_id=87)

        with self.assertRaises(InvalidRomError):
            parse_map_header_table(
                header_data, {88: "PALLET TOWN"}, header_ids=[0], archive_path="0x0"
            )


class ParseGmapgroupsPointersTests(unittest.TestCase):
    def test_decodes_group_count_pointers(self) -> None:
        pointers = tuple(0x08350000 + index * 4 for index in range(_GROUP_COUNT))
        data = struct.pack(f"<{_GROUP_COUNT}I", *pointers)

        decoded = parse_gmapgroups_pointers(data, group_count=_GROUP_COUNT)

        self.assertEqual(decoded, pointers)

    def test_rejects_wrong_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_gmapgroups_pointers(b"\x00" * 10, group_count=_GROUP_COUNT)


_GBA = 0x08000000


def _map_rom(*arrays: tuple[int, tuple[int, ...]]) -> bytearray:
    """A ROM with three map headers at 0x100, 0x120, and 0x140 sharing one
    1x1 layout at 0x200, plus each `(offset, entries)` pointer array.
    """
    rom = bytearray(0x400)
    struct.pack_into("<2i4I", rom, 0x200, 1, 1, *(_GBA + 0x200,) * 4)
    for header in (0x100, 0x120, 0x140):
        struct.pack_into("<I", rom, header, _GBA + 0x200)
    for offset, entries in arrays:
        struct.pack_into(f"<{len(entries)}I", rom, offset, *entries)
    return rom


def _reader(rom: bytes | bytearray) -> Callable[[int, int], bytes]:
    def read(offset: int, size: int) -> bytes:
        if offset + size > len(rom):
            raise InvalidRomError("out of range")
        return bytes(rom[offset : offset + size])

    return read


class ParseMapGroupIndexTests(unittest.TestCase):
    def test_bounds_contiguous_groups_by_the_next_array(self) -> None:
        # Retail layout: group 0 has 2 maps and group 1 has 1, packed back
        # to back and ending at gMapGroups (0x30C).
        rom = _map_rom((0x300, (_GBA + 0x100, _GBA + 0x120, _GBA + 0x140)))

        index = parse_map_group_index(
            (_GBA + 0x300, _GBA + 0x308),
            _reader(rom),
            gmapgroups_address=_GBA + 0x30C,
        )

        self.assertEqual(
            index,
            {(0, 0): _GBA + 0x100, (0, 1): _GBA + 0x120, (1, 0): _GBA + 0x140},
        )

    def test_ends_a_group_at_its_first_entry_that_is_not_a_map_header(
        self,
    ) -> None:
        # A hack moved gMapGroups to 0x380 and added group 1 at 0x3A0, so
        # group 0 runs into the old table (pointers to arrays, not headers)
        # and nothing bounds group 1.
        rom = _map_rom(
            (0x300, (_GBA + 0x100, _GBA + 0x300)),
            (0x3A0, (_GBA + 0x120, _GBA + 0x140, 0)),
        )

        index = parse_map_group_index(
            (_GBA + 0x300, _GBA + 0x3A0),
            _reader(rom),
            gmapgroups_address=_GBA + 0x380,
        )

        self.assertEqual(
            index,
            {(0, 0): _GBA + 0x100, (1, 0): _GBA + 0x120, (1, 1): _GBA + 0x140},
        )

    def test_rejects_a_group_without_map_headers(self) -> None:
        rom = _map_rom((0x300, (0,)))

        with self.assertRaisesRegex(InvalidRomError, "group 0 has no map headers"):
            parse_map_group_index(
                (_GBA + 0x300,), _reader(rom), gmapgroups_address=_GBA + 0x304
            )


class CountMapGroupsTests(unittest.TestCase):
    def test_counts_the_leading_rom_pointers(self) -> None:
        data = struct.pack("<4I", 0x08350000, 0x08350010, 0x08350020, 2)

        count = count_map_groups(lambda offset, size: data[offset : offset + size], 0)

        self.assertEqual(count, 3)

    def test_rejects_a_table_without_groups(self) -> None:
        with self.assertRaises(InvalidRomError):
            count_map_groups(lambda offset, size: bytes(size), 0)


if __name__ == "__main__":
    unittest.main()
