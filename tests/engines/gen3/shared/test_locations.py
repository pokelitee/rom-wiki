from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.locations import (
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


class ParseMapGroupIndexTests(unittest.TestCase):
    def test_resolves_group_num_to_header_address_using_boundaries(self) -> None:
        # Two groups: group 0 has 2 maps, group 1 has 1 map. Sub-table data
        # (the raw pointer bytes spanning group_pointers[0] to
        # gmapgroups_address) holds 3 header-address pointers back to back.
        group_pointers = (0x08350000, 0x08350008)
        gmapgroups_address = 0x0835000C
        subtable_data = struct.pack("<3I", 0x08360000, 0x08360020, 0x08360040)

        index = parse_map_group_index(
            group_pointers, subtable_data, gmapgroups_address=gmapgroups_address
        )

        self.assertEqual(index[(0, 0)], 0x08360000)
        self.assertEqual(index[(0, 1)], 0x08360020)
        self.assertEqual(index[(1, 0)], 0x08360040)

    def test_rejects_a_misaligned_group_boundary(self) -> None:
        group_pointers = (0x08350000, 0x08350003)
        with self.assertRaises(InvalidRomError):
            parse_map_group_index(
                group_pointers, b"\x00" * 8, gmapgroups_address=0x08350008
            )


if __name__ == "__main__":
    unittest.main()
