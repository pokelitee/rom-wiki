from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.platforms.nds.reader import NintendoDSImage, _validate_regions
from romwiki.util.errors import InvalidRomError
from tests.conftest import make_header

# make_header() declares: ARM9 at 0x4000 (size 0x100), ARM7 at 0x5000 (size
# 0x100), file name table at 0x6000 (size 0x100), file allocation table at
# 0x7000 (size 0x40) -- the file allocation table is the last region, so this
# is the minimum image size every declared region fits inside.
_MINIMUM_VALID_IMAGE_SIZE = 0x7000 + 0x40


class NintendoDSImageInspectTests(unittest.TestCase):
    def test_inspects_a_well_formed_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.nds"
            path.write_bytes(make_header() + bytes(_MINIMUM_VALID_IMAGE_SIZE - 0x200))

            image = NintendoDSImage.inspect(path)

            self.assertEqual(image.header.title, "POKEMON PL")
            self.assertEqual(image.size, _MINIMUM_VALID_IMAGE_SIZE)
            self.assertEqual(len(image.hashes.sha256), 64)
            self.assertEqual(len(image.hashes.md5), 32)

    def test_rejects_a_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.nds"
            with self.assertRaisesRegex(InvalidRomError, "does not exist"):
                NintendoDSImage.inspect(path)

    def test_rejects_an_image_too_short_for_its_declared_regions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.nds"
            # Shorter than the file allocation table's declared end (0x7040).
            path.write_bytes(make_header() + bytes(0x1000 - 0x200))

            with self.assertRaisesRegex(InvalidRomError, "extends past the end"):
                NintendoDSImage.inspect(path)

    def test_to_dict_reports_source_name_size_hashes_and_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rom.nds"
            path.write_bytes(make_header() + bytes(_MINIMUM_VALID_IMAGE_SIZE - 0x200))
            image = NintendoDSImage.inspect(path)

            value = image.to_dict()

            self.assertEqual(value["source_name"], "rom.nds")
            self.assertEqual(value["size"], _MINIMUM_VALID_IMAGE_SIZE)
            self.assertIn("sha256", value["hashes"])
            self.assertEqual(value["header"]["title"], "POKEMON PL")


class ValidateRegionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.header = NintendoDSHeader.from_bytes(make_header())

    def test_accepts_an_image_that_fits_every_declared_region(self) -> None:
        _validate_regions(self.header, _MINIMUM_VALID_IMAGE_SIZE)  # does not raise

    def test_rejects_an_image_that_cuts_off_the_file_allocation_table(self) -> None:
        with self.assertRaisesRegex(
            InvalidRomError, "file allocation table extends past"
        ):
            _validate_regions(self.header, _MINIMUM_VALID_IMAGE_SIZE - 1)

    def test_rejects_an_image_that_cuts_off_arm9(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "ARM9 extends past"):
            _validate_regions(self.header, self.header.arm9_offset)


if __name__ == "__main__":
    unittest.main()
