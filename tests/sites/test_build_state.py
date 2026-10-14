from __future__ import annotations

import os
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

from romwiki.sites import GameMetadata, SiteCatalog, SiteDefinition, build_sites
from romwiki.sites.build_state import current_site_build_state, site_build_fingerprint


class SiteBuildFingerprintTests(unittest.TestCase):
    def test_content_fingerprint_ignores_mtimes_but_tracks_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, site, page = _make_site(root)
            output = root / "dist"
            original = _fingerprint(catalog, site, output)
            _shift_mtime(page)
            after_touch = _fingerprint(catalog, site, output)
            page.write_text("# Changed\n", encoding="utf-8")
            after_edit = _fingerprint(catalog, site, output)

        self.assertEqual(after_touch, original)
        self.assertNotEqual(after_edit, original)

    def test_default_fingerprint_keeps_the_metadata_fast_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, site, page = _make_site(root)
            output = root / "dist"
            original = _fingerprint(catalog, site, output, hash_contents=False)
            _shift_mtime(page)
            after_touch = _fingerprint(catalog, site, output, hash_contents=False)

        self.assertNotEqual(after_touch, original)

    def test_configuration_fingerprint_tracks_locked_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, site, _ = _make_site(root)
            requirements = root / "requirements" / "docs.txt"
            requirements.parent.mkdir()
            requirements.write_text("mkdocs==1.0\n", encoding="utf-8")
            output = root / "dist"
            original = _fingerprint(catalog, site, output)
            requirements.write_text("mkdocs==2.0\n", encoding="utf-8")
            updated = _fingerprint(catalog, site, output)

        self.assertNotEqual(updated, original)

    def test_content_reuse_survives_mtime_resets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, site, page = _make_site(root)
            output = root / "dist"
            commands: list[tuple[str, ...]] = []

            def build(command: Sequence[str]) -> None:
                commands.append(tuple(command))
                destination = Path(command[-1])
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "index.html").write_text("ok", encoding="utf-8")

            for _ in range(2):
                build_sites(
                    catalog,
                    output,
                    site_ids=(site.id,),
                    reuse_unchanged=True,
                    hash_contents=True,
                    state_root=root / "state",
                    runner=build,
                )
                _shift_mtime(page)

        self.assertEqual(len(commands), 1)


def _fingerprint(
    catalog: SiteCatalog,
    site: SiteDefinition,
    output: Path,
    *,
    hash_contents: bool = True,
) -> str:
    return site_build_fingerprint(
        current_site_build_state(
            catalog,
            site,
            output,
            dev=False,
            site_url=None,
            hash_contents=hash_contents,
        )
    )


def _shift_mtime(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))


def _make_site(root: Path) -> tuple[SiteCatalog, SiteDefinition, Path]:
    site_root = root / "sites" / "games" / "example"
    wiki_root = site_root / "wiki"
    wiki_root.mkdir(parents=True)
    config = site_root / "mkdocs.yml"
    config.write_text("site_name: Example\n", encoding="utf-8")
    page = wiki_root / "index.md"
    page.write_text("# Example\n", encoding="utf-8")
    site = SiteDefinition(
        id="example",
        name="Example",
        kind="game",
        slug="example",
        published=True,
        order=1,
        config_path=config,
        description="Example",
        theme="platinum",
        game=GameMetadata(
            profiles=(),
            versions=(),
            data_driven=False,
            generation=4,
            base_game="platinum",
            platform="nintendo-ds",
            platform_name="Nintendo DS",
            creator="Tester",
        ),
    )
    return SiteCatalog(root, (site,)), site, page
