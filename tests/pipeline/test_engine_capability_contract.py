from __future__ import annotations

import unittest
from pathlib import Path

from romwiki.pipeline.build_context import GameBuildContext
from romwiki.pipeline.identify import inspect_rom
from romwiki.profiles.loader import ProfileRepository
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry

_PROFILES_DIR = Path("profiles")
_GAMES_CONFIG = Path(".local/games.toml")
_POKEDB_ROOTS = {
    "gen4_dppt": Path("../pokedb/.output/gen4"),
    "gen5_bw": Path("../pokedb/.output/gen5"),
}


class EngineCapabilityContractTests(unittest.TestCase):
    """Every optional dataset a profile's `layout`/`parameters` turns on must
    be backed by an engine module that actually implements it.

    `EngineAdapter` requires every field to point at *some* module for every
    engine (see `engines/registry.py`), even concerns that engine doesn't
    implement -- nothing at the type level stops a profile from enabling a
    slice its own engine's module lacks the parser for; that would only
    surface as an `AttributeError` the first time someone tries to build
    that profile. Rather than hand-mapping every gating key to its required
    function (fragile, and it'd duplicate each extractor's own branching),
    this drives the real pipeline end-to-end against the real ROM for every
    currently configured profile, so a wiring mismatch fails here instead of
    at first `build family` run. Skipped per-profile when its ROM
    isn't available locally (matching `test_cli.py`'s own precedent), so
    this suite still runs in environments without ROM fixtures.
    """

    def test_every_profile_builds_all_dataset_kinds_from_its_real_rom(self) -> None:
        profiles = ProfileRepository.load(_PROFILES_DIR).profiles
        if not _GAMES_CONFIG.is_file():
            self.skipTest(
                "local game configuration is not available in this environment"
            )
        registry = LocalGameRegistry.load(_GAMES_CONFIG)

        exercised = 0
        for profile in profiles:
            try:
                rom_path = registry.get(profile.id).rom()
            except LocalConfigError:
                continue
            pokedb_root = _POKEDB_ROOTS.get(profile.engine)
            if pokedb_root is None or not pokedb_root.is_dir():
                continue
            with self.subTest(profile=profile.id):
                result = inspect_rom(rom_path, _PROFILES_DIR)
                self.assertIsNotNone(
                    result.match, f"{profile.id}'s own ROM fixture no longer matches it"
                )
                context = GameBuildContext(result, PokeDBGeneration.load(pokedb_root))
                datasets = context.all_datasets()
                for kind, dataset in datasets.items():
                    if dataset is not None:
                        self.assertIn("record_count", dataset, f"{profile.id}/{kind}")
            exercised += 1

        if exercised == 0:
            self.skipTest("no configured profile has a local ROM fixture available")


if __name__ == "__main__":
    unittest.main()
