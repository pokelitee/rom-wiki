from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.errors import SiteError
from romwiki.sites import SiteCatalog, build_sites


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SiteCatalogTests(unittest.TestCase):
    def test_loads_portal_and_game_sites_in_display_order(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        self.assertEqual(
            [site.id for site in catalog.sites],
            ["portal", "renegade-platinum"],
        )
        self.assertEqual(catalog.get("renegade-platinum").slug, "renegade-platinum")

    def test_build_all_targets_one_combined_artifact(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)
        commands: list[tuple[str, ...]] = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dist"

            built = build_sites(
                catalog,
                output,
                build_all=True,
                runner=lambda command: commands.append(tuple(command)),
            )

            self.assertEqual([site.id for site in built], ["portal", "renegade-platinum"])
            self.assertEqual(Path(commands[0][-1]), output.resolve())
            self.assertEqual(
                Path(commands[1][-1]), output.resolve() / "renegade-platinum"
            )

    def test_build_requires_an_explicit_selection(self) -> None:
        catalog = SiteCatalog.load(REPOSITORY_ROOT)

        with self.assertRaises(SiteError):
            build_sites(catalog, Path("dist"), runner=lambda command: None)


if __name__ == "__main__":
    unittest.main()
