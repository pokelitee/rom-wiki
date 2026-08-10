from __future__ import annotations

import shlex
import unittest
from pathlib import Path

from romwiki.cli import build_parser
from romwiki.sites import SiteCatalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_engine_data_source_partials_have_explicit_consumers(self) -> None:
        consumers = {
            "gen4-dppt-data-sources.md": {
                "platinum",
                "renegade-platinum",
            },
            "gen5-bw-data-sources.md": {
                "black-white",
                "blaze-black-volt-white",
            },
            "gen5-b2w2-data-sources.md": {
                "black-2-white-2",
                "blaze-black-2-volt-white-2",
            },
        }
        game_pages = {
            path.parent.parent.name: path.read_text(encoding="utf-8")
            for path in (REPOSITORY_ROOT / "sites/games").glob("*/wiki/data-sources.md")
        }

        for partial_name, expected_consumers in consumers.items():
            partial = REPOSITORY_ROOT / "sites/shared/partials" / partial_name
            self.assertTrue(partial.is_file())
            partial_text = partial.read_text(encoding="utf-8")
            for heading in (
                "## Pokémon species data",
                "## Items",
                "## Moves",
                "## Wild encounters",
                "## Trainers",
                "## Locations",
                "## Text and names",
            ):
                self.assertIn(heading, partial_text)
            directive = f'--8<-- "{partial_name}"'
            actual_consumers = {
                site_id for site_id, page in game_pages.items() if directive in page
            }
            with self.subTest(partial=partial_name):
                self.assertEqual(actual_consumers, expected_consumers)

        self.assertFalse(
            (REPOSITORY_ROOT / "sites/shared/partials/gen4-data-sources.md").exists()
        )

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

    def test_generation_five_coverage_notes_match_supported_links(self) -> None:
        shared_bw_notes = (
            REPOSITORY_ROOT / "sites/shared/partials/gen5-bw-data-sources.md"
        ).read_text(encoding="utf-8")
        shared_b2w2_notes = (
            REPOSITORY_ROOT / "sites/shared/partials/gen5-b2w2-data-sources.md"
        ).read_text(encoding="utf-8")

        for stale_claim in (
            "there's no map location to link these to yet",
            "these aren't linked to a specific map location",
        ):
            self.assertNotIn(stale_claim, shared_bw_notes)
        for supported_scope in (
            "These relationships are published in both directions.",
            "Selectors `0` through `19` link those persistent inventories",
            "selector `255` marks a standard Poké Mart",
        ):
            self.assertIn(supported_scope, shared_bw_notes)
        for limitation in (
            "**Roaming Pokémon:**",
            "**B2W2 phone trades:**",
        ):
            self.assertNotIn(limitation, shared_bw_notes)
        self.assertIn("**Black/White roaming Pokémon:**", shared_bw_notes)
        self.assertNotIn("Curtis/Yancy", shared_bw_notes)
        self.assertIn("complete 30-item catalog", shared_bw_notes)
        self.assertNotIn("**Black City market stock:**", shared_bw_notes)

        for site_id in ("black-2-white-2", "blaze-black-2-volt-white-2"):
            notes = (
                REPOSITORY_ROOT / f"sites/games/{site_id}/wiki/data-sources.md"
            ).read_text(encoding="utf-8")
            with self.subTest(site=site_id):
                self.assertIn('--8<-- "gen5-b2w2-data-sources.md"', notes)
                self.assertNotIn("## Known coverage limitations", notes)
                self.assertNotIn("Curtis/Yancy repeat trades", notes)

        for supported_scope in (
            "first 709 archive members",
            "60-entry tutor table",
            "`0` through `25`",
            "selectors `253` and `254`",
            "Black City's four conditional market stores",
            "Curtis/Yancy trades",
            "published as Xtransceiver",
            "not roaming encounters",
        ):
            self.assertIn(supported_scope, shared_b2w2_notes)

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
