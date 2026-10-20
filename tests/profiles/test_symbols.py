from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from romwiki.engines.gen3.shared.battle_variants import REMATCH_ENTRY_SIZE
from romwiki.engines.gen3.shared.constants import (
    ENCOUNTER_HEADER_SIZE,
    ITEM_RECORD_SIZE,
    MOVE_RECORD_SIZE,
    PERSONAL_RECORD_SIZE,
    TRAINER_RECORD_SIZE,
)
from romwiki.engines.gen3.shared.trades import INGAME_TRADE_SIZE
from romwiki.engines.gen4.platinum.map_headers import MAP_HEADER_SIZE
from romwiki.engines.gen4.platinum.rematch import REMATCH_RECORD_SIZE
from romwiki.engines.gen4.platinum.tutors import TUTOR_RECORD_SIZE
from romwiki.profiles.loader import ProfileRepository

_PROFILES = Path(__file__).resolve().parents[2] / "profiles"
_NAME_SIZE = {"move_name": 13, "ability_name": 13}
_REGION_NAME_ENTRY_SIZE = {"firered-us": 4, "leafgreen-us": 4, "emerald-us": 8}

# `<count parameter>: (<offset parameter>, entry size in bytes, terminator rows)`.
_COUNTS = {
    "personal_count": ("personal_offset", PERSONAL_RECORD_SIZE, 0),
    "move_count": ("move_offset", MOVE_RECORD_SIZE, 0),
    "item_count": ("item_offset", ITEM_RECORD_SIZE, 0),
    "trainer_count": ("trainer_offset", TRAINER_RECORD_SIZE, 0),
    "move_name_count": ("move_name_offset", _NAME_SIZE["move_name"], 0),
    "ability_name_count": ("ability_name_offset", _NAME_SIZE["ability_name"], 0),
    "encounter_count": ("encounter_offset", ENCOUNTER_HEADER_SIZE, 1),
    "rematch_table_count": ("rematch_table_offset", REMATCH_ENTRY_SIZE, 0),
    "trade_count": ("trade_table_offset", INGAME_TRADE_SIZE, 0),
    "machine_count": ("machine_move_offset", 2, 0),
    "egg_move_table_size": ("egg_move_offset", 1, 0),
}


# Platinum's 4-byte (item, value) rows.
_PAIR_SIZE = 4
_PLATINUM_COUNTS = {
    "map_header_count": ("map_header_offset", MAP_HEADER_SIZE, 0),
    "trainer_rematch_count": ("trainer_rematch_offset", REMATCH_RECORD_SIZE, 0),
    "tutor_count": ("tutor_move_offset", TUTOR_RECORD_SIZE, 0),
    "game_corner_prize_count": ("game_corner_prize_table_offset", _PAIR_SIZE, 0),
    "fossil_revival_count": ("fossil_revival_table_offset", _PAIR_SIZE, 0),
    "frontier_price_record_count": ("frontier_price_table_offset", _PAIR_SIZE, 0),
}
# Platinum offset parameter -> the parameter naming the overlay it is read from.
_PLATINUM_OVERLAYS = {
    "trainer_class_prize_offset": "trainer_class_prize_overlay_id",
    "trainer_rematch_offset": "trainer_rematch_overlay_id",
    "egg_move_offset": "egg_move_overlay_id",
    "tutor_move_offset": "tutor_overlay_id",
    "tutor_compatibility_offset": "tutor_overlay_id",
    "frontier_price_table_offset": "frontier_price_overlay_id",
    "pickup_common_items_offset": "pickup_overlay_id",
    "pickup_rare_items_offset": "pickup_overlay_id",
    "pickup_common_rate_offset": "pickup_overlay_id",
    "pickup_honey_gather_rate_offset": "pickup_overlay_id",
}


class RetailSymbolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profiles = {
            profile.id: profile
            for profile in ProfileRepository.load(_PROFILES).profiles
        }

    def _symbols(self, profile_id: str) -> dict[str, dict[str, int]]:
        path = _PROFILES / "symbols" / f"{profile_id}.toml"
        symbols: dict[str, dict[str, int]] = tomllib.loads(path.read_text("utf-8"))[
            "symbols"
        ]
        return symbols

    def _assert_counts(
        self, profile_id: str, counts: dict[str, tuple[str, int, int]]
    ) -> None:
        profile, table = self.profiles[profile_id], self._symbols(profile_id)
        for count, (offset, entry_size, terminators) in counts.items():
            with self.subTest(profile=profile_id, count=count):
                size = table[profile.symbols[offset]]["size"]
                self.assertEqual(
                    profile.int_parameter(count), size // entry_size - terminators
                )
                self.assertEqual(size % entry_size, 0)

    def test_gen3_counts_match_pret_symbol_sizes(self) -> None:
        for profile_id, region_size in _REGION_NAME_ENTRY_SIZE.items():
            self._assert_counts(
                profile_id,
                {
                    **_COUNTS,
                    "region_name_count": ("region_name_offset", region_size, 0),
                },
            )

    def test_platinum_counts_match_pret_symbol_sizes(self) -> None:
        self._assert_counts("platinum-us", _PLATINUM_COUNTS)

    def test_platinum_symbols_sit_in_the_overlays_profiles_read(self) -> None:
        profile, table = self.profiles["platinum-us"], self._symbols("platinum-us")
        for offset, symbol in profile.symbols.items():
            with self.subTest(offset=offset):
                overlay = _PLATINUM_OVERLAYS.get(offset)
                self.assertEqual(
                    table[symbol].get("overlay"),
                    None if overlay is None else profile.int_parameter(overlay),
                )


if __name__ == "__main__":
    unittest.main()
