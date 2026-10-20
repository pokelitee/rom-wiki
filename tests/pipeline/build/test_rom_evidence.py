from __future__ import annotations

import os
import re
import tomllib
import unittest
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

from romwiki.engines.gen3.shared.scripts import GOTO, TERMINATORS
from romwiki.engines.registry import get_engine
from romwiki.pipeline.extraction.identify import InspectionResult, inspect_rom
from romwiki.pipeline.extraction.locations.gba_map_events import map_scripts
from romwiki.pipeline.extraction.map_headers import iter_gba_map_headers
from romwiki.pipeline.extraction.reference_names import (
    extract_reference_descriptions,
)
from romwiki.platforms.registry import get_platform
from romwiki.profiles.loader import ProfileRepository
from romwiki.profiles.models import GameProfile, TableLocation
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry

_ROOT = Path(__file__).resolve().parents[3]
_PROFILES_DIR = _ROOT / "profiles"
_GAMES_CONFIG = _ROOT / ".local/games.toml"
_ENABLE = "ROMWIKI_ROM_TESTS"
_GEN3_ENGINES = frozenset({"gen3_frlg", "gen3_emerald"})
_GEN4_ENGINES = frozenset({"gen4_platinum", "gen4_hgss"})
# The right Pokédex bank matches PokéDB's text for its own version for 86-91%
# of species; a sibling version's bank matches 40-51%.
_MIN_POKEDEX_MATCH = 0.8


@unittest.skipUnless(
    os.environ.get(_ENABLE) == "1",
    f"real-ROM checks need local ROMs; set {_ENABLE}=1 to run them",
)
class RomEvidenceTests(unittest.TestCase):
    """The facts profiles and engines rely on, checked against each local ROM.

    Each of these was first established by hand against the real ROMs; keeping
    them as tests means a profile or engine change that breaks one fails here.
    """

    registry: LocalGameRegistry
    profiles: tuple[GameProfile, ...]
    retail_tables: set[str]

    @classmethod
    def setUpClass(cls) -> None:
        if not _GAMES_CONFIG.is_file():
            raise AssertionError(
                f"{_ENABLE}=1 requires a local game registry: {_GAMES_CONFIG}"
            )
        cls.registry = LocalGameRegistry.load(_GAMES_CONFIG)
        cls.profiles = ProfileRepository.load(_PROFILES_DIR).profiles
        cls.retail_tables = {
            path.stem for path in (_PROFILES_DIR / "symbols").glob("*.toml")
        }

    def _inspected(self, engines: frozenset[str]) -> Iterator[InspectionResult]:
        found = 0
        for profile in self.profiles:
            if profile.engine not in engines:
                continue
            try:
                rom_path = self.registry.get(profile.id).rom()
            except LocalConfigError:
                continue
            result = inspect_rom(rom_path, _PROFILES_DIR)
            self.assertIsNotNone(result.match, profile.id)
            found += 1
            yield result
        if found == 0:
            self.fail(f"no {sorted(engines)} profile in {_GAMES_CONFIG} has a ROM")

    def _gen3_maps(
        self, result: InspectionResult
    ) -> tuple[GameProfile, Any, list[dict[int, Any]]]:
        assert result.match is not None
        profile = result.match.profile
        engine = get_engine(profile.engine).locations
        platform = get_platform(profile.platform)
        assert platform.read_bytes is not None
        rom = platform.read_bytes(result.image, 0, result.image.size)
        read: Callable[[int, int], bytes] = lambda offset, size: rom[
            offset : offset + size
        ]
        scripts = [
            map_scripts(engine, read, header)
            for header in iter_gba_map_headers(engine, platform, result.image, profile)
        ]
        return profile, engine, scripts

    def test_gen3_tables_are_where_their_code_points(self) -> None:
        for result in self._inspected(_GEN3_ENGINES):
            assert result.match is not None
            profile = result.match.profile
            with self.subTest(profile=profile.id):
                self.assertEqual(profile.table_locations.keys(), profile.symbols.keys())
                expected = (
                    {TableLocation.SYMBOL}
                    if profile.id in self.retail_tables
                    else {TableLocation.SYMBOL, TableLocation.POINTER}
                )
                self.assertLessEqual(set(profile.table_locations.values()), expected)

    def test_gen3_encounter_tables_end_where_pret_sizes_them(self) -> None:
        # Encounter counts come from the table's 0xFF terminator; for retail
        # builds that must leave exactly the terminator row of pret's table.
        for result in self._inspected(_GEN3_ENGINES):
            assert result.match is not None
            profile = result.match.profile
            if profile.id not in self.retail_tables:
                continue
            engine = get_engine(profile.engine).encounters
            platform = get_platform(profile.platform)
            assert platform.read_bytes is not None
            read = platform.read_bytes
            symbols = tomllib.loads(
                (_PROFILES_DIR / "symbols" / f"{profile.id}.toml").read_text("utf-8")
            )["symbols"]
            size = symbols[profile.symbols["encounter_offset"].name]["size"]
            with self.subTest(profile=profile.id):
                count = engine.count_encounter_headers(
                    partial(read, result.image),
                    profile.int_parameter("encounter_offset"),
                )
                self.assertEqual(count, size // engine.ENCOUNTER_HEADER_SIZE - 1)

    def test_every_reachable_gen3_script_decodes(self) -> None:
        for result in self._inspected(_GEN3_ENGINES):
            profile, engine, scripts = self._gen3_maps(result)
            stops = TERMINATORS | engine.SCRIPT_WARP_COMMANDS | {GOTO}
            instructions = {
                address: instruction
                for map_scripts_ in scripts
                for address, instruction in map_scripts_.items()
            }
            with self.subTest(profile=profile.id):
                self.assertTrue(instructions)
                undecoded = sorted(
                    hex(address)
                    for address, instruction in instructions.items()
                    if instruction.opcode not in stops
                    and instruction.next_offset not in instructions
                )
                self.assertEqual(undecoded, [])

    def test_gen3_specials_find_every_trade_and_event_pokemon(self) -> None:
        for result in self._inspected(_GEN3_ENGINES):
            profile, engine, scripts = self._gen3_maps(result)
            trade_count = profile.int_parameter("trade_count")
            species_count = profile.int_parameter("personal_count")
            trades: set[int] = set()
            event_pokemon = 0
            for instructions in scripts:
                trades.update(
                    trade
                    for trade, _ in engine.find_trades(
                        instructions,
                        trade_count=trade_count,
                        trade_info_special=profile.int_parameter("trade_info_special"),
                    )
                )
                event_pokemon += len(
                    engine.find_pokemon(
                        instructions,
                        species_count=species_count,
                        event_mon_special=profile.int_parameter("event_mon_special"),
                    )
                ) - len(
                    engine.find_pokemon(
                        instructions,
                        species_count=species_count,
                        event_mon_special=None,
                    )
                )
            with self.subTest(profile=profile.id):
                self.assertEqual(trades, set(range(trade_count)))
                self.assertGreater(event_pokemon, 0)

    def test_gen4_pokedex_banks_match_their_own_version(self) -> None:
        pokedb_root = self.registry.pokedb_root
        if pokedb_root is None:
            self.fail(f"{_ENABLE}=1 requires pokedb_root in {_GAMES_CONFIG}")
        pokedb = PokeDBGeneration.load(pokedb_root / "gen4")
        for result in self._inspected(_GEN4_ENGINES):
            assert result.match is not None
            profile = result.match.profile
            if "pokemon_descriptions_member" not in profile.parameters:
                continue
            platform = get_platform(profile.platform)
            assert platform.filesystem_from_image is not None
            filesystem = platform.filesystem_from_image(result.image)
            texts = extract_reference_descriptions(
                profile, filesystem, fields={"pokemon_descriptions"}
            )["pokemon_descriptions"]
            compared = matched = 0
            for species, text in enumerate(texts):
                flavor = pokedb.pokemon_by_id.get(species, {}).get("flavor_text") or {}
                expected = flavor.get(profile.base_game)
                if species == 0 or not text or not isinstance(expected, str):
                    continue
                compared += 1
                matched += _normalized(expected) == _normalized(text)
            with self.subTest(profile=profile.id):
                self.assertGreater(compared, 0)
                self.assertGreaterEqual(matched / compared, _MIN_POKEDEX_MATCH)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("­", "")).strip().lower()


if __name__ == "__main__":
    unittest.main()
