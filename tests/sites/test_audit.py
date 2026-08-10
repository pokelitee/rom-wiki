from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from romwiki.sites.audit import _PARALLEL_PAGE_THRESHOLD, audit_site
from romwiki.util.errors import SiteError


class SiteAuditTests(unittest.TestCase):
    def test_reuses_parsed_pages_by_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "audit.sqlite3"
            _write_page(root / "index.html", "<p>Cached</p>")
            audit_site(root, cache_path=cache, jobs=1)

            with patch("romwiki.sites.audit._parse_page") as parse:
                report = audit_site(root, cache_path=cache, jobs=1)

        self.assertTrue(report.ok)
        parse.assert_not_called()

    def test_validates_the_expected_artifact_file_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", "<p>Index</p>")
            (root / "extra.txt").write_text("extra", encoding="utf-8")

            report = audit_site(
                root, expected_files={"index.html", "missing.txt"}
            )

        self.assertEqual(
            {issue.code for issue in report.errors},
            {"artifact-missing", "artifact-unexpected"},
        )

    def test_rejects_markdown_source_links_in_published_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "index.html",
                '<a href="types/index.md#fire">Fire</a>',
            )
            markdown = root / "types" / "index.md"
            markdown.parent.mkdir(parents=True)
            markdown.write_text("# Types\n", encoding="utf-8")

            report = audit_site(root)

        self.assertEqual(
            [issue.code for issue in report.errors],
            ["published-markdown-link"],
        )

    def test_accepts_accessible_pages_and_valid_local_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "index.html",
                '<a class="rw-link" href="detail/#facts">Detail</a>',
            )
            _write_page(
                root / "detail" / "index.html",
                """
                <h2 id="facts">Facts</h2>
                <img src="https://example.test/sprite.png" alt="Sprite" loading="lazy">
                <details><summary>Source</summary><p>ROM</p></details>
                <table><thead><tr><th>Field</th></tr></thead></table>
                """,
            )
            assets = root / "assets"
            assets.mkdir()
            (assets / "site.css").write_text(
                ".rw-link { color: blue; }", encoding="utf-8"
            )

            report = audit_site(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.page_count, 2)
        self.assertEqual(report.link_count, 1)

    def test_accepts_minified_bareword_alt_attribute(self) -> None:
        # mkdocs.base.yml's minify_html plugin collapses alt="" down to the
        # valueless boolean-attribute form `alt`; the audit must still
        # recognize it as present rather than reporting a false positive.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "index.html",
                "<img class=rw-table-sprite src=sprite.png alt loading=lazy>",
            )

            report = audit_site(root)

        self.assertNotIn("image-alt", {issue.code for issue in report.errors})

    def test_resolves_minified_unquoted_href_id_and_class_attributes(self) -> None:
        # minify_html also drops quotes around attribute values with no
        # whitespace/quote/`=`/angle-bracket characters (e.g. `href=detail/`
        # instead of `href="detail/"`); link counting, link-target
        # validation, duplicate-id detection, and custom-class usage must all
        # still work against that unquoted form.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "index.html",
                "<a class=rw-link href=detail/#facts>Detail</a>",
            )
            _write_page(
                root / "detail" / "index.html",
                "<h2 id=facts>Facts</h2>",
            )
            assets = root / "assets"
            assets.mkdir()
            (assets / "site.css").write_text(
                ".rw-link { color: blue; }", encoding="utf-8"
            )

            report = audit_site(root)

        self.assertTrue(report.ok, [issue.format() for issue in report.errors])
        self.assertEqual(report.link_count, 1)

    def test_reports_broken_structure_links_and_custom_styles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                """
                <!doctype html><html><head><title>Broken</title></head><body>
                <main><h1 id="same">Broken</h1><h3 id="same">Jump</h3>
                <a href="missing/#nowhere">Missing</a>
                <img class="rw-unstyled" src="image.png">
                <details><p>No summary</p></details>
                <table><tr><td>No heading</td></tr></table>
                </main></body></html>
                """,
                encoding="utf-8",
            )
            (root / "site.css").write_text(".rw-unused {}", encoding="utf-8")

            report = audit_site(root)

        codes = {issue.code for issue in (*report.errors, *report.warnings)}
        self.assertIn("document-lang", codes)
        self.assertIn("duplicate-id", codes)
        self.assertIn("heading-order", codes)
        self.assertIn("link-target", codes)
        self.assertIn("image-alt", codes)
        self.assertIn("details-summary", codes)
        self.assertIn("table-header", codes)
        self.assertIn("css-unused", codes)

    def test_ignores_conditionally_rendered_fallback_styles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", "")
            (root / "site.css").write_text(
                """
                .rw-party-card__gender--unknown {}
                .rw-party-card__moves-empty {}
                .rw-record-tree__placeholder {}
                .rw-actually-unused {}
                """,
                encoding="utf-8",
            )

            report = audit_site(root)

        css_warnings = [
            issue for issue in report.warnings if issue.code == "css-unused"
        ]
        self.assertEqual(len(css_warnings), 1)
        self.assertIn("rw-actually-unused", css_warnings[0].message)

    def test_enforces_page_size_limit_and_warns_on_image_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "index.html",
                '<img src="one.png" alt=""><img src="two.png" alt="">',
            )

            report = audit_site(root, max_html_bytes=10, max_images_per_page=1)

        self.assertEqual({issue.code for issue in report.errors}, {"page-size"})
        self.assertIn("image-count", {issue.code for issue in report.warnings})

    def test_resolves_directory_and_site_root_links_in_combined_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", '<a href="./">Home</a>')
            _write_page(
                root / "game" / "index.html",
                '<a href="../">Portal</a><a href="/pokemon/">Pokémon</a>',
            )
            _write_page(
                root / "game" / "pokemon" / "index.html",
                '<a href="../../">Portal</a>',
            )

            report = audit_site(root)

        self.assertTrue(report.ok, [issue.format() for issue in report.errors])

    def test_resolves_links_below_a_deployment_base_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", '<a href="/rom-wiki/">Home</a>')
            _write_page(
                root / "game" / "index.html",
                '<a href="/rom-wiki/game/">Game</a>',
            )

            report = audit_site(
                root, base_url="https://example.test/rom-wiki/"
            )

        self.assertTrue(report.ok, [issue.format() for issue in report.errors])

    def test_accepts_nested_page_link_to_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(
                root / "pokemon" / "bulbasaur" / "index.html",
                '<a href="../../abilities/overgrow/#effects">Effects</a>',
            )
            _write_page(
                root / "abilities" / "overgrow" / "index.html",
                '<span id="effects">Effects</span>',
            )

            report = audit_site(root)

        self.assertTrue(report.ok, [issue.format() for issue in report.errors])

    def test_parallel_and_serial_parsing_agree(self) -> None:
        # Enough pages to cross the threshold where audit_site parses in
        # worker processes, so both code paths are exercised on one artifact.
        page_count = _PARALLEL_PAGE_THRESHOLD + 10
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", '<a href="page-0/">First</a>')
            for index in range(page_count):
                _write_page(
                    root / f"page-{index}" / "index.html",
                    f'<a href="../missing-{index}/">Broken</a>',
                )

            parallel = audit_site(root, jobs=4)
            serial = audit_site(root, jobs=1)

        self.assertEqual(parallel.page_count, page_count + 1)
        self.assertEqual(parallel.page_count, serial.page_count)
        self.assertEqual(parallel.link_count, serial.link_count)
        self.assertEqual(parallel.total_html_bytes, serial.total_html_bytes)
        self.assertEqual(parallel.largest_page, serial.largest_page)
        self.assertEqual(
            sorted(issue.format() for issue in parallel.errors),
            sorted(issue.format() for issue in serial.errors),
        )
        self.assertEqual(len(parallel.errors), page_count)

    def test_rejects_a_job_count_below_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_page(root / "index.html", "<p>Only page</p>")

            with self.assertRaises(SiteError):
                audit_site(root, jobs=0)


def _write_page(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<!doctype html><html lang="en"><head><title>Test</title></head>'
        f"<body><main><h1>Test</h1>{content}</main></body></html>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
