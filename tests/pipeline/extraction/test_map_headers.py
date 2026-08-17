from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from romwiki.pipeline.extraction.map_headers import (
    code_load_address,
    parse_map_header_table,
    read_code_binary,
    resolve_map_headers,
)
from romwiki.util.errors import DataSourceError, InvalidRomError


class ReadCodeBinaryTests(unittest.TestCase):
    def test_reads_the_compressed_code_binary_by_default(self) -> None:
        platform = SimpleNamespace(read_code_binary=lambda image: b"compressed-code")

        result = read_code_binary(platform, "image")

        self.assertEqual(result, b"compressed-code")

    def test_ignores_the_decompressed_reader_when_no_engine_is_given(self) -> None:
        platform = SimpleNamespace(
            read_code_binary=lambda image: b"compressed-code",
            read_decompressed_code_binary=lambda image: b"decompressed-code",
        )

        result = read_code_binary(platform, "image")

        self.assertEqual(result, b"compressed-code")

    def test_reads_the_decompressed_code_binary_when_the_engine_requests_it(
        self,
    ) -> None:
        platform = SimpleNamespace(
            read_code_binary=lambda image: b"compressed-code",
            read_decompressed_code_binary=lambda image: b"decompressed-code",
        )
        engine = SimpleNamespace(CODE_BINARY_DECOMPRESSED=True)

        result = read_code_binary(platform, "image", engine)

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
        engine = SimpleNamespace(CODE_BINARY_DECOMPRESSED=True)

        with self.assertRaises(DataSourceError):
            read_code_binary(platform, "image", engine)


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


if __name__ == "__main__":
    unittest.main()
