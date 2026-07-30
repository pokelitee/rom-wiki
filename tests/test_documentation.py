from __future__ import annotations

import shlex
import unittest
from pathlib import Path

from romwiki.cli import build_parser
from romwiki.sites import SiteCatalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_published_game_overviews_follow_the_documentation_contract(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        for site in catalog.published():
            if site.kind != "game":
                continue
            site_root = site.config_path.parent
            index = (site_root / "wiki/index.md").read_text(encoding="utf-8")
            data_sources = (site_root / "wiki/data-sources.md").read_text(
                encoding="utf-8"
            )
            navigation = site.config_path.read_text(encoding="utf-8")
            normalized_index = " ".join(index.split())

            with self.subTest(site=site.id):
                self.assertTrue(index.startswith("---\ntemplate: game-home.html\n"))
                self.assertIn("This wiki covers", index)
                self.assertIn("published as", index)
                self.assertIn(
                    "ROM provenance and PokéDB reference content are kept distinct",
                    normalized_index,
                )
                self.assertTrue(data_sources.startswith("# Data sources\n"))
                self.assertRegex(data_sources, r"(?m)^## Primary ROMs?$")
                for heading in (
                    "## Publication model",
                    "## Coverage and provenance",
                    "## Engine notes",
                ):
                    self.assertIn(heading, data_sources)
                for entry in (
                    "Home: index.md",
                    "Data Sources: data-sources.md",
                    "Data Downloads: data/index.md",
                    "Game Data:",
                ):
                    self.assertIn(entry, navigation)
                self.assertIn(
                    "  - World:\n"
                    "      - Wild Encounters: encounters/index.md\n"
                    "      - Trainers: trainers/index.md\n"
                    "      - Locations: locations/index.md\n",
                    navigation,
                )

    def test_documented_cli_commands_parse(self) -> None:
        parser = build_parser()
        paths = [
            REPOSITORY_ROOT / "README.md",
            *(REPOSITORY_ROOT / "docs").rglob("*.md"),
        ]
        commands = []
        for path in paths:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if line.startswith("romwiki "):
                    commands.append((path, line_number, line))

        self.assertTrue(commands)
        for path, line_number, command in commands:
            with self.subTest(path=path, line=line_number):
                parser.parse_args(shlex.split(command, posix=False)[1:])


if __name__ == "__main__":
    unittest.main()
