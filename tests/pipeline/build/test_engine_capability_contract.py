from __future__ import annotations

import os
import unittest
from pathlib import Path

from romwiki.engines.registry import get_engine
from romwiki.pipeline.build.checks import find_dataset_problems
from romwiki.pipeline.build.context import GameBuildContext
from romwiki.pipeline.extraction.identify import inspect_rom
from romwiki.profiles.loader import ProfileRepository
from romwiki.sites import SiteCatalog
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import LocalConfigError
from romwiki.util.local_config import LocalGameRegistry

_ROOT = Path(__file__).resolve().parents[3]
_PROFILES_DIR = _ROOT / "profiles"
_GAMES_CONFIG = _ROOT / ".local/games.toml"
_ENABLE = "ROMWIKI_ROM_TESTS"


@unittest.skipUnless(
    os.environ.get(_ENABLE) == "1",
    f"real-ROM builds take minutes; set {_ENABLE}=1 to run them",
)
class EngineCapabilityContractTests(unittest.TestCase):
    """Build every locally registered profile from its real ROM.

    `EngineAdapter` requires every field to point at *some* module for every
    engine (see `engines/registry.py`), even concerns that engine doesn't
    implement -- nothing at the type level stops a profile from enabling a
    slice its own engine's module lacks the parser for; that would only
    surface as an `AttributeError` the first time someone tries to build
    that profile. Rather than hand-mapping every gating key to its required
    function (fragile, and it'd duplicate each extractor's own branching),
    this drives the real pipeline end-to-end against the real ROM for every
    configured profile, so a wiring mismatch fails here instead of at the
    first `generate` run. Profiles of published sites must also pass the
    content checks; unpublished partial engines only need to build.
    """

    def test_every_profile_builds_all_dataset_kinds_from_its_real_rom(self) -> None:
        if not _GAMES_CONFIG.is_file():
            self.fail(f"{_ENABLE}=1 requires a local game registry: {_GAMES_CONFIG}")
        registry = LocalGameRegistry.load(_GAMES_CONFIG)
        if registry.pokedb_root is None:
            self.fail(f"{_ENABLE}=1 requires pokedb_root in {_GAMES_CONFIG}")
        published = {
            profile
            for site in SiteCatalog.load(_ROOT).published()
            if site.game is not None
            for profile in site.game.profiles
        }

        exercised = 0
        for profile in ProfileRepository.load(_PROFILES_DIR).profiles:
            try:
                rom_path = registry.get(profile.id).rom()
            except LocalConfigError:
                continue
            generation = get_engine(profile.engine).generation
            with self.subTest(profile=profile.id):
                result = inspect_rom(rom_path, _PROFILES_DIR)
                self.assertIsNotNone(
                    result.match, f"{profile.id}'s own ROM fixture no longer matches it"
                )
                pokedb = PokeDBGeneration.load(
                    registry.pokedb_root / f"gen{generation}"
                )
                datasets = GameBuildContext(result, pokedb).all_datasets()
                for kind, dataset in datasets.items():
                    self.assertIn("record_count", dataset, f"{profile.id}/{kind}")
                if profile.id in published:
                    self.assertEqual(find_dataset_problems(datasets), [])
            exercised += 1

        if exercised == 0:
            self.fail(f"no profile in {_GAMES_CONFIG} has a local ROM")


if __name__ == "__main__":
    unittest.main()
