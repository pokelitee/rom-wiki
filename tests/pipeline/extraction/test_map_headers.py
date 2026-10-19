from __future__ import annotations

import struct
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import romwiki.engines.gen3.frlg as frlg
from romwiki.pipeline.extraction.map_headers import (
    code_load_address,
    iter_gba_map_headers,
    parse_map_header_table,
    read_code_binary,
    resolve_map_headers,
)
from romwiki.profiles.models import GameProfile
from romwiki.util.errors import DataSourceError, InvalidRomError


class ReadCodeBinaryTests(unittest.TestCase):
    def test_reads_the_compressed_code_binary_by_default(self) -> None:
        platform = SimpleNamespace(read_code_binary=lambda image: b"compressed-code")

        result = read_code_binary(platform, "image")

        self.assertEqual(result, b"compressed-code")

    def test_ignores_the_decompressed_reader_unless_compressed(self) -> None:
        platform = SimpleNamespace(
            read_code_binary=lambda image: b"compressed-code",
            read_decompressed_code_binary=lambda image: b"decompressed-code",
        )

        result = read_code_binary(platform, "image")

        self.assertEqual(result, b"compressed-code")

    def test_reads_the_decompressed_code_binary_when_compressed(
        self,
    ) -> None:
        platform = SimpleNamespace(
            read_code_binary=lambda image: b"compressed-code",
            read_decompressed_code_binary=lambda image: b"decompressed-code",
        )

        result = read_code_binary(platform, "image", compressed=True)

        self.assertEqual(result, b"decompressed-code")

    def test_raises_when_the_platform_exposes_no_code_binary(self) -> None:
        platform = SimpleNamespace(read_code_binary=None)

        with self.assertRaises(DataSourceError):
            read_code_binary(platform, "image")

    def test_raises_when_the_platform_exposes_no_decompressed_code_binary(
        self,
    ) -> None:
        platform = SimpleNamespace(
            read_code_binary=lambda image: b"compressed-code",
            read_decompressed_code_binary=None,
        )

        with self.assertRaises(DataSourceError):
            read_code_binary(platform, "image", compressed=True)


class CodeLoadAddressTests(unittest.TestCase):
    def test_returns_the_platforms_load_address(self) -> None:
        platform = SimpleNamespace(code_load_address=lambda image: 0x02000000)

        self.assertEqual(code_load_address(platform, "image"), 0x02000000)

    def test_raises_when_the_platform_exposes_no_load_address(self) -> None:
        platform = SimpleNamespace(code_load_address=None)

        with self.assertRaises(DataSourceError):
            code_load_address(platform, "image")


class ParseMapHeaderTableTests(unittest.TestCase):
    def test_slices_the_arm9_blob_at_the_configured_table_offset(self) -> None:
        parse_map_headers = Mock(return_value=("header-0", "header-1"))
        engine = SimpleNamespace(MAP_HEADER_SIZE=4, parse_map_headers=parse_map_headers)
        arm9_data = bytes(range(32))
        filesystem = SimpleNamespace(
            read=lambda path: b"names" if path == "map_names.bin" else b""
        )

        result = parse_map_header_table(
            engine, arm9_data, filesystem, "map_names.bin", table_offset=4, count=3
        )

        self.assertEqual(result, ("header-0", "header-1"))
        parse_map_headers.assert_called_once_with(arm9_data[4:16], b"names", count=3)


class ResolveMapHeadersTests(unittest.TestCase):
    def test_resolves_each_headers_location_name(self) -> None:
        headers = (
            SimpleNamespace(header_id=0, location_name_id=0),
            SimpleNamespace(header_id=1, location_name_id=1),
        )
        engine = SimpleNamespace(
            MAP_HEADER_SIZE=1,
            parse_map_headers=lambda header_data, names, count: headers,
            parse_english_message_archive=lambda data: ("Town A", "Town B"),
        )
        arm9_data = bytes(2)
        filesystem = SimpleNamespace(read=lambda path: b"")
        messages = SimpleNamespace(read=lambda member: b"location-names")

        resolved_headers, location_names = resolve_map_headers(
            engine,
            arm9_data,
            filesystem,
            messages,
            map_names_path="map_names.bin",
            table_offset=0,
            count=2,
            location_names_member=7,
        )

        self.assertEqual(resolved_headers, headers)
        self.assertEqual(location_names, ("Town A", "Town B"))

    def test_raises_when_a_header_references_a_missing_location_name(self) -> None:
        headers = (SimpleNamespace(header_id=0, location_name_id=5),)
        engine = SimpleNamespace(
            MAP_HEADER_SIZE=1,
            parse_map_headers=lambda header_data, names, count: headers,
            parse_english_message_archive=lambda data: ("Only Town",),
        )
        filesystem = SimpleNamespace(read=lambda path: b"")
        messages = SimpleNamespace(read=lambda member: b"location-names")

        with self.assertRaises(InvalidRomError):
            resolve_map_headers(
                engine,
                bytes(1),
                filesystem,
                messages,
                map_names_path="map_names.bin",
                table_offset=0,
                count=1,
                location_names_member=7,
            )


_GBA = 0x08000000


def _gba_map_rom() -> tuple[bytes, GameProfile]:
    """A ROM with two map groups (two maps, then one) and two Kanto names.

    Layout: names at 0x00, `sMapNames` at 0x40, three map headers at 0x80,
    each group's header-pointer array at 0x100, and `gMapGroups` at 0x10C.
    """
    rom = bytearray(0x200)
    rom[0x00:0x05] = bytes([0xCA, 0xBB, 0xC6, 0xC6, 0xFF])  # PALL
    rom[0x10:0x14] = bytes([0xD0, 0xC3, 0xCC, 0xFF])  # VIR
    struct.pack_into("<2I", rom, 0x40, _GBA + 0x00, _GBA + 0x10)
    for index, section in enumerate((89, 88, 89)):
        rom[0x80 + 28 * index + 0x14] = section
    struct.pack_into("<3I", rom, 0x100, _GBA + 0x80, _GBA + 0x80 + 28, _GBA + 0x80 + 56)
    struct.pack_into("<2I", rom, 0x10C, _GBA + 0x100, _GBA + 0x108)
    profile = GameProfile(
        id="test-gba",
        name="Test",
        platform="game-boy-advance",
        engine="gen3_frlg",
        base_game="firered",
        game_codes=(),
        rom_versions=(),
        hashes=(),
        layout={},
        parameters={
            "gmapgroups_offset": 0x10C,
            "map_group_count": 2,
            "region_name_offset": 0x40,
            "region_name_count": 2,
        },
    )
    return bytes(rom), profile


class IterGbaMapHeadersTests(unittest.TestCase):
    def test_numbers_every_map_in_group_order_with_its_section_name(self) -> None:
        rom, profile = _gba_map_rom()
        platform = SimpleNamespace(
            read_bytes=lambda image, offset, size: rom[offset : offset + size]
        )

        headers = list(iter_gba_map_headers(frlg, platform, None, profile))

        self.assertEqual(
            [
                (header.header_id, header.map_group, header.map_num, header.name)
                for header in headers
            ],
            [(0, 0, 0, "VIR"), (1, 0, 1, "PALL"), (2, 1, 0, "VIR")],
        )
        self.assertEqual(headers[1].rom_offset, 0x80 + 28)

    def test_skips_maps_in_an_unnamed_section_but_keeps_their_ids(self) -> None:
        rom, profile = _gba_map_rom()
        # Terminate the VIR name at once, leaving section 89 unnamed.
        rom = rom[:0x10] + b"\xff" + rom[0x11:]
        platform = SimpleNamespace(
            read_bytes=lambda image, offset, size: rom[offset : offset + size]
        )

        headers = list(iter_gba_map_headers(frlg, platform, None, profile))

        self.assertEqual(
            [(header.header_id, header.name) for header in headers], [(1, "PALL")]
        )

    def test_rejects_a_map_in_an_unknown_section(self) -> None:
        rom, profile = _gba_map_rom()
        profile = replace(
            profile, parameters={**profile.parameters, "region_name_count": 1}
        )
        platform = SimpleNamespace(
            read_bytes=lambda image, offset, size: rom[offset : offset + size]
        )

        with self.assertRaisesRegex(InvalidRomError, "unknown region map section 89"):
            list(iter_gba_map_headers(frlg, platform, None, profile))


if __name__ == "__main__":
    unittest.main()
