from __future__ import annotations

import unittest

from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem, NintendoDSImage
from romwiki.platforms.registry import get_platform
from romwiki.util.errors import DataSourceError


class PlatformRegistryTests(unittest.TestCase):
    def test_gets_the_nintendo_ds_adapter(self) -> None:
        adapter = get_platform("nintendo-ds")

        self.assertEqual(adapter.inspect, NintendoDSImage.inspect)
        self.assertEqual(adapter.filesystem_from_image, NintendoDSFileSystem.from_image)
        self.assertIs(adapter.archive_cls, NarcArchive)
        self.assertIsNotNone(adapter.read_overlay)

    def test_rejects_an_unknown_platform(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "Unsupported platform"):
            get_platform("game-boy-color")


if __name__ == "__main__":
    unittest.main()
