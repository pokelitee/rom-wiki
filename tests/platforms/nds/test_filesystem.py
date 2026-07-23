from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from romwiki.platforms.nds.filesystem import NintendoDSFileSystem
from romwiki.platforms.nds.header import NintendoDSHeader
from romwiki.platforms.nds.reader import NintendoDSImage, RomHashes
from tests.conftest import make_header


class NintendoDSFileSystemTests(unittest.TestCase):
    def test_reads_a_file_in_a_nested_directory(self) -> None:
        header_data = bytearray(make_header())
        fnt = bytearray(34)
        struct.pack_into("<IHH", fnt, 0, 16, 0, 2)
        struct.pack_into("<IHH", fnt, 8, 24, 0, 0xF000)
        fnt[16:24] = b"\x84data\x01\xF0\0"
        fnt[24:34] = b"\x08test.bin\0"
        struct.pack_into("<II", header_data, 0x40, 0x200, len(fnt))
        struct.pack_into("<II", header_data, 0x48, 0x300, 8)

        image_data = bytearray(0x1004)
        image_data[:0x200] = header_data
        image_data[0x200 : 0x200 + len(fnt)] = fnt
        struct.pack_into("<II", image_data, 0x300, 0x1000, 0x1004)
        image_data[0x1000:0x1004] = b"NARC"

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "test.nds"
            image_path.write_bytes(image_data)
            image = NintendoDSImage(
                path=image_path,
                size=len(image_data),
                header=NintendoDSHeader.from_bytes(header_data),
                hashes=RomHashes(md5="", sha1="", sha256=""),
            )

            filesystem = NintendoDSFileSystem.from_image(image)

            self.assertEqual(len(filesystem.files), 1)
            self.assertEqual(filesystem.get("data/test.bin").id, 0)
            self.assertEqual(filesystem.read("data/test.bin"), b"NARC")


if __name__ == "__main__":
    unittest.main()
