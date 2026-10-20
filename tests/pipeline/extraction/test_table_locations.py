from __future__ import annotations

import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from romwiki.pipeline.extraction.table_locations import locate_tables
from romwiki.profiles.models import (
    GameProfile,
    HashMatch,
    KnownHash,
    TableLocation,
    TableSymbol,
)

_GBA = 0x08000000
_TABLE = 0x100
_SITES = (0x10, 0x20)


def _match() -> HashMatch:
    profile = GameProfile(
        id="test-gba",
        name="Test",
        platform="game-boy-advance",
        engine="gen3_frlg",
        base_game="firered",
        game_codes=(),
        rom_versions=(),
        hashes=(),
        parameters={"table_offset": _TABLE, "explicit_offset": 0x40},
        symbols={
            "table_offset": TableSymbol(
                name="gTable", address=_GBA + _TABLE, pointers=_SITES
            )
        },
    )
    return HashMatch(profile=profile, known_hash=KnownHash("sha256", "test", "test"))


class LocateTablesTests(unittest.TestCase):
    def _locate(self, words: dict[int, int], match: HashMatch) -> GameProfile:
        rom = bytearray(0x200)
        for site, word in words.items():
            struct.pack_into("<I", rom, site, word)
        image: Any = SimpleNamespace(
            path=Path("test.gba"), size=len(rom), data=bytes(rom)
        )
        return locate_tables(match, image).profile

    def test_confirms_a_table_every_site_still_points_to(self) -> None:
        profile = self._locate(dict.fromkeys(_SITES, _GBA + _TABLE), _match())

        self.assertEqual(profile.parameters["table_offset"], _TABLE)
        self.assertEqual(profile.table_locations["table_offset"], TableLocation.SYMBOL)

    def test_follows_a_table_every_site_was_repointed_to(self) -> None:
        profile = self._locate(dict.fromkeys(_SITES, _GBA + 0x180), _match())

        self.assertEqual(profile.parameters["table_offset"], 0x180)
        self.assertEqual(profile.table_locations["table_offset"], TableLocation.POINTER)

    def test_keeps_the_symbol_offset_when_the_sites_disagree(self) -> None:
        words = {_SITES[0]: _GBA + 0x180, _SITES[1]: _GBA + _TABLE}

        profile = self._locate(words, _match())

        self.assertEqual(profile.parameters["table_offset"], _TABLE)
        self.assertEqual(
            profile.table_locations["table_offset"],
            TableLocation.SYMBOL_UNCONFIRMED,
        )

    def test_keeps_the_symbol_offset_when_the_sites_point_outside_the_rom(
        self,
    ) -> None:
        profile = self._locate(dict.fromkeys(_SITES, _GBA + 0x1000), _match())

        self.assertEqual(profile.parameters["table_offset"], _TABLE)
        self.assertEqual(
            profile.table_locations["table_offset"],
            TableLocation.SYMBOL_UNCONFIRMED,
        )

    def test_leaves_explicit_offsets_alone(self) -> None:
        profile = self._locate(dict.fromkeys(_SITES, _GBA + 0x180), _match())

        self.assertEqual(profile.parameters["explicit_offset"], 0x40)
        self.assertNotIn("explicit_offset", profile.table_locations)


if __name__ == "__main__":
    unittest.main()
