from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.bw.locations import (
    parse_map_header_script_files,
    parse_map_header_table,
    parse_wild_map_names,
)
from romwiki.util.errors import InvalidRomError

_MAP_NAMES = ("Route 1", "Route 2", "Accumula Town")


def _map_header(
    *, name_index: int, wild_set: int, script_file: int = 0, matrix_id: int = 0
) -> bytes:
    record = bytearray(48)
    record[26] = name_index
    struct.pack_into("<H", record, 20, wild_set)
    struct.pack_into("<H", record, 6, script_file)
    struct.pack_into("<H", record, 4, matrix_id)
    return bytes(record)


class Gen5LocationsTests(unittest.TestCase):
    def test_maps_wild_set_to_map_names(self) -> None:
        data = (
            _map_header(name_index=0, wild_set=5)
            + _map_header(name_index=2, wild_set=0xFFFF)
            + _map_header(name_index=1, wild_set=6)
        )

        result = parse_wild_map_names(data, map_names=_MAP_NAMES)

        self.assertEqual(result, {5: ["Route 1"], 6: ["Route 2"]})

    def test_collects_multiple_distinct_names_per_wild_set(self) -> None:
        data = (
            _map_header(name_index=0, wild_set=5)
            + _map_header(name_index=1, wild_set=5)
            + _map_header(name_index=0, wild_set=5)
        )

        result = parse_wild_map_names(data, map_names=_MAP_NAMES)

        self.assertEqual(result, {5: ["Route 1", "Route 2"]})

    def test_ignores_the_null_wild_set(self) -> None:
        data = _map_header(name_index=0, wild_set=0xFFFF)
        self.assertEqual(parse_wild_map_names(data, map_names=_MAP_NAMES), {})

    def test_rejects_an_invalid_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_wild_map_names(b"short", map_names=_MAP_NAMES)

    def test_rejects_a_missing_map_name(self) -> None:
        data = _map_header(name_index=99, wild_set=5)
        with self.assertRaises(InvalidRomError):
            parse_wild_map_names(data, map_names=_MAP_NAMES)

    def test_parses_the_full_header_table(self) -> None:
        data = _map_header(name_index=0, wild_set=5) + _map_header(
            name_index=2, wild_set=0xFFFF
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[0].header_id, 0)
        self.assertEqual(headers[0].name, "Route 1")
        self.assertEqual(headers[0].encounter_map_index, 5)
        self.assertEqual(headers[0].provenance.archive, "maps.narc")
        self.assertEqual(headers[0].provenance.member, 0)
        self.assertEqual(headers[1].name, "Accumula Town")
        self.assertIsNone(headers[1].encounter_map_index)

    def test_parses_each_header_s_own_script_file_index(self) -> None:
        # Real Black ROM fact: map header 7 (Striaton City) points at script
        # archive member 14, whose function-table entry 4 (NPC scriptUsed=4,
        # 1-indexed) is Cilan's tutorial `CallTrainerBattle` -- see
        # gen5/bw/overworld.py's module docstring for the full cross-check.
        data = _map_header(name_index=0, wild_set=5, script_file=14) + _map_header(
            name_index=1, wild_set=6, script_file=310
        )

        self.assertEqual(parse_map_header_script_files(data), (14, 310))

    def test_parses_each_header_s_own_matrix_id(self) -> None:
        # Real Black ROM fact: header 317 (Route 1), 319 (Route 2), and 389
        # (Nuvema Town's outdoor plaza) all report matrix 0 -- see
        # gen5/bw/map_matrices.py's module docstring for the full
        # cross-check against that matrix's own header-ID grid.
        data = _map_header(name_index=0, wild_set=5, matrix_id=0) + _map_header(
            name_index=1, wild_set=6, matrix_id=39
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertEqual(headers[0].matrix_id, 0)
        self.assertEqual(headers[1].matrix_id, 39)


if __name__ == "__main__":
    unittest.main()
