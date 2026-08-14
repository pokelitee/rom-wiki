from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from romwiki.pipeline.build.regeneration import (
    can_reuse_generation,
    write_regeneration_state,
)
from romwiki.sites.catalog import GameMetadata, SiteDefinition


class RegenerationStateTests(unittest.TestCase):
    def test_reuses_only_an_exact_generated_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site_root = root / "site"
            generated = site_root / "wiki" / "pokemon" / "index.md"
            generated.parent.mkdir(parents=True)
            generated.write_text("# Pokemon\n", encoding="utf-8")
            site = SiteDefinition(
                "game",
                "Game",
                "game",
                "game",
                True,
                1,
                site_root / "mkdocs.yml",
                "",
                "platinum",
                GameMetadata(
                    ("game",), (), True, 4, "base", "nds", "NDS", "Test", ("pokemon",)
                ),
            )
            state = root / "state.json"
            write_regeneration_state(state, "input", site)

            self.assertTrue(can_reuse_generation(state, "input", site))
            generated.write_text("changed\n", encoding="utf-8")
            self.assertFalse(can_reuse_generation(state, "input", site))
            self.assertFalse(can_reuse_generation(state, "other", site))


if __name__ == "__main__":
    unittest.main()
