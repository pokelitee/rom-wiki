from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from romwiki.platforms.gba.reader import GbaImage, read_bytes
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_gba_header

_EXTRA_DATA = b"\xab\xcd\xef\x01" * 16


class GbaImageInspectTests(unittest.TestCase):
    def test_inspects_a_well_formed_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header() + _EXTRA_DATA)

            image = GbaImage.inspect(path)

            self.assertEqual(image.header.game_code, "BPRE")
            self.assertEqual(image.size, 0xC0 + len(_EXTRA_DATA))
            self.assertEqual(len(image.hashes.sha256), 64)
            self.assertEqual(len(image.hashes.md5), 32)

    def test_rejects_a_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.gba"
            with self.assertRaisesRegex(InvalidRomError, "does not exist"):
                GbaImage.inspect(path)

    def test_rejects_an_image_too_short_for_a_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header()[:0x10])
            with self.assertRaises(InvalidRomError):
                GbaImage.inspect(path)

    def test_hashes_the_whole_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            content = make_gba_header() + _EXTRA_DATA
            path.write_bytes(content)

            image = GbaImage.inspect(path)

            self.assertEqual(image.hashes.sha256, hashlib.sha256(content).hexdigest())

    def test_rejects_an_image_larger_than_the_cartridge_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            with path.open("wb") as stream:
                stream.write(make_gba_header())
                stream.truncate(0x2000000 + 1)

            with self.assertRaisesRegex(InvalidRomError, "larger than 32 MiB"):
                GbaImage.inspect(path)

    def test_to_dict_reports_source_name_size_hashes_and_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header() + _EXTRA_DATA)
            image = GbaImage.inspect(path)

            value = image.to_dict()

            self.assertEqual(value["source_name"], "rom.gba")
            self.assertEqual(value["size"], 0xC0 + len(_EXTRA_DATA))
            self.assertIn("sha256", value["hashes"])
            self.assertEqual(value["header"]["game_code"], "BPRE")


class ReadBytesTests(unittest.TestCase):
    def test_reads_a_slice_at_an_offset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header() + _EXTRA_DATA)
            image = GbaImage.inspect(path)

            data = read_bytes(image, 0xC0, 4)

            self.assertEqual(data, _EXTRA_DATA[:4])

    def test_reads_from_the_image_read_at_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header() + _EXTRA_DATA)
            image = GbaImage.inspect(path)
            path.unlink()

            self.assertEqual(read_bytes(image, 0xC0, 4), _EXTRA_DATA[:4])

    def test_rejects_a_read_past_the_end_of_the_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.gba"
            path.write_bytes(make_gba_header() + _EXTRA_DATA)
            image = GbaImage.inspect(path)

            with self.assertRaises(InvalidRomError):
                read_bytes(image, 0xC0, len(_EXTRA_DATA) + 1)


if __name__ == "__main__":
    unittest.main()
